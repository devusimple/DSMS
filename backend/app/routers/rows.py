"""Row CRUD endpoints (parameterized, generated via sqlgen module)."""

from __future__ import annotations

import numbers

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.db import ops
from app.db.manager import ConnectionRecord
from app.routers.deps import get_connection
from app.schemas import RowAction, RowsOut
from app.sqlgen import delete_row_sql, insert_row_sql, update_row_sql

router = APIRouter()


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


@router.get(
    "/connections/{conn_id}/tables/{table_name}/rows", response_model=RowsOut
)
def list_rows(
    conn_id: str,
    table_name: str,
    record: ConnectionRecord = Depends(get_connection),
) -> RowsOut:
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
    columns, rows = ops.fetch_rows(record, table_name)
    return RowsOut(columns=columns, rows=[_json_values(r) for r in rows])


@router.post(
    "/connections/{conn_id}/tables/{table_name}/rows", status_code=201
)
def insert_row(
    conn_id: str,
    table_name: str,
    payload: RowAction,
    record: ConnectionRecord = Depends(get_connection),
) -> dict:
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
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
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
    if not payload.pk:
        raise HTTPException(status_code=422, detail="pk is required for updates.")
    statement, params = update_row_sql(table_name, payload.data, payload.pk, record.dialect)
    return _execute(record, statement, params)


@router.delete("/connections/{conn_id}/tables/{table_name}/rows")
def delete_row(
    conn_id: str,
    table_name: str,
    payload: RowAction,
    record: ConnectionRecord = Depends(get_connection),
) -> dict:
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
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
