"""Row CRUD endpoints (parameterized, generated via sqlgen module)."""

from __future__ import annotations

import json
import numbers

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from api.db import ops
from api.db.manager import ConnectionRecord
from api.routers.deps import get_connection
from api.schemas import RowAction, RowsOut
from api.sqlgen import (
    count_rows_sql,
    delete_row_sql,
    insert_row_sql,
    select_rows_sql,
    update_row_sql,
)

router = APIRouter()

#: Rows per page when pagination is requested without an explicit page size.
DEFAULT_PAGE_SIZE = 25


def _json_values(data: dict) -> dict:
    """Convert python values to JSON-serializable primitives for the API."""
    out = {}
    for k, v in data.items():
        if isinstance(v, bool):
            out[k] = v
        elif isinstance(v, numbers.Integral):
            out[k] = int(v)
        elif isinstance(v, numbers.Real):
            out[k] = float(v)
        elif v is None:
            out[k] = None
        else:
            out[k] = str(v)
    return out


@router.get("/connections/{conn_id}/tables/{table_name}/rows", response_model=RowsOut)
def list_rows(
    conn_id: str,
    table_name: str,
    page: int | None = None,
    page_size: int | None = None,
    order_by: str | None = None,
    order_dir: str = "asc",
    search: str | None = None,
    where: str | None = None,
    record: ConnectionRecord = Depends(get_connection),
) -> RowsOut:
    """List rows with optional server-side pagination/sort/filter.

    Without any of these parameters the full table is returned (legacy
    behaviour). ``where`` is a JSON array of ``[column, operator, value]``
    triples (same operators as the SQL generator).
    """
    if not ops.table_exists(record, table_name):
        raise HTTPException(
            status_code=404, detail=f"Table {table_name!r} does not exist."
        )

    where_filters: list[tuple[str, str, object]] | None = None
    if where:
        try:
            raw = json.loads(where)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid where JSON: {exc}"
            ) from exc
        if not isinstance(raw, list) or not all(
            isinstance(item, list)
            and len(item) == 3
            and isinstance(item[0], str)
            and isinstance(item[1], str)
            for item in raw
        ):
            raise HTTPException(
                status_code=400,
                detail="where must be a JSON array of [column, operator, value] rows.",
            )
        where_filters = [(item[0], item[1], item[2]) for item in raw]

    paginated = (
        page is not None or page_size is not None or search or where_filters or order_by
    )
    if not paginated:
        columns, rows = ops.fetch_rows(record, table_name)
        return RowsOut(
            columns=columns, rows=[_json_values(r) for r in rows], total=len(rows)
        )

    table_columns = [c.name for c in ops.reflect_table(record, table_name).columns]
    try:
        statement, params = select_rows_sql(
            table_name,
            order_by=order_by,
            order_dir=order_dir,
            search=search,
            search_columns=table_columns if search else None,
            where=where_filters,
            page=page or 1,
            page_size=page_size or DEFAULT_PAGE_SIZE,
            dialect=record.dialect,
        )
        count_stmt, count_params = count_rows_sql(
            table_name,
            search=search,
            search_columns=table_columns if search else None,
            where=where_filters,
            dialect=record.dialect,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        with record.engine.connect() as conn:
            rows = [
                _json_values(dict(row))
                for row in conn.execute(text(statement), params).mappings()
            ]
            total = int(conn.execute(text(count_stmt), count_params).scalar() or 0)
    except Exception as exc:  # noqa: BLE001 - surface driver errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RowsOut(columns=table_columns, rows=rows, total=total)


@router.post("/connections/{conn_id}/tables/{table_name}/rows", status_code=201)
def insert_row(
    conn_id: str,
    table_name: str,
    payload: RowAction,
    record: ConnectionRecord = Depends(get_connection),
) -> dict:
    if not ops.table_exists(record, table_name):
        raise HTTPException(
            status_code=404, detail=f"Table {table_name!r} does not exist."
        )
    statement, params = insert_row_sql(table_name, payload.data, record.dialect)
    return _execute(record, statement, params, status=201)


@router.put("/connections/{conn_id}/tables/{table_name}/rows")
def update_row(
    conn_id: str,
    table_name: str,
    payload: RowAction,
    record: ConnectionRecord = Depends(get_connection),
) -> dict:
    if not ops.table_exists(record, table_name):
        raise HTTPException(
            status_code=404, detail=f"Table {table_name!r} does not exist."
        )
    if not payload.pk:
        raise HTTPException(status_code=422, detail="pk is required for updates.")
    statement, params = update_row_sql(
        table_name, payload.data, payload.pk, record.dialect
    )
    return _execute(record, statement, params)


@router.delete("/connections/{conn_id}/tables/{table_name}/rows")
def delete_row(
    conn_id: str,
    table_name: str,
    payload: RowAction,
    record: ConnectionRecord = Depends(get_connection),
) -> dict:
    if not ops.table_exists(record, table_name):
        raise HTTPException(
            status_code=404, detail=f"Table {table_name!r} does not exist."
        )
    if not payload.pk:
        raise HTTPException(status_code=422, detail="pk is required for deletes.")
    statement, params = delete_row_sql(table_name, payload.pk, record.dialect)
    return _execute(record, statement, params)


def _execute(record: ConnectionRecord, statement: str, params: dict, status: int = 200):
    try:
        with record.engine.begin() as conn:
            result = conn.execute(text(statement), params)
    except Exception as exc:  # noqa: BLE001 - surface driver errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"rowcount": result.rowcount, "statement": statement}
