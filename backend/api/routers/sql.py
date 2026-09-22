"""Arbitrary SQL execution and structured SQL generation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from api.db.manager import ConnectionRecord
from api.routers.deps import get_connection
from api.schemas import GeneratedSqlWithParams, GenerateSql, SqlResult, SqlRun
from api.sqlgen import (
    count_rows_sql,
    delete_row_sql,
    insert_row_sql,
    select_rows_sql,
    update_row_sql,
    upsert_row_sql,
)

router = APIRouter()


@router.post("/connections/{conn_id}/sql", response_model=SqlResult)
def run_sql(
    conn_id: str,
    payload: SqlRun,
    record: ConnectionRecord = Depends(get_connection),
) -> SqlResult:
    params = payload.params or {}
    try:
        with record.engine.begin() as conn:
            result = conn.execute(text(payload.statement), params)
    except Exception as exc:  # noqa: BLE001 - surface driver errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result.returns_rows:
        return SqlResult(columns=[], rows=[], rowcount=result.rowcount or 0)

    columns = list(result.keys())
    rows = [[_to_json_value(value) for value in row] for row in result.fetchall()]
    return SqlResult(columns=columns, rows=rows, rowcount=result.rowcount or len(rows))


@router.post("/connections/{conn_id}/generate", response_model=GeneratedSqlWithParams)
def generate_sql(
    conn_id: str,
    payload: GenerateSql,
    record: ConnectionRecord = Depends(get_connection),
) -> GeneratedSqlWithParams:
    """Build a SQL statement from structured options (no execution).

    Mirrors the frontend query builder; the connection is used only for its
    dialect so identifiers are quoted correctly.
    """
    dialect = record.dialect
    try:
        if payload.verb == "select":
            sql, params = select_rows_sql(
                payload.table,
                payload.columns,
                eq=payload.eq,
                where=payload.where,
                search=payload.search,
                search_columns=payload.search_columns,
                distinct=payload.distinct,
                order_by=payload.order_by,
                order_dir=payload.order_dir,
                limit=payload.limit,
                offset=payload.offset,
                page=payload.page,
                page_size=payload.page_size,
                dialect=dialect,
            )
        elif payload.verb == "count":
            sql, params = count_rows_sql(
                payload.table,
                eq=payload.eq,
                where=payload.where,
                search=payload.search,
                search_columns=payload.search_columns,
                distinct_columns=payload.columns,
                dialect=dialect,
            )
        elif payload.verb == "insert":
            sql, params = insert_row_sql(payload.table, payload.data or {}, dialect)
        elif payload.verb == "update":
            sql, params = update_row_sql(
                payload.table, payload.data or {}, payload.pk or {}, dialect
            )
        elif payload.verb == "delete":
            sql, params = delete_row_sql(payload.table, payload.pk or {}, dialect)
        elif payload.verb == "upsert":
            sql, params = upsert_row_sql(
                payload.table,
                payload.data or {},
                payload.conflict_columns or [],
                dialect,
            )
        else:  # pragma: no cover - guarded by the Literal
            raise ValueError(f"Unknown verb {payload.verb!r}.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GeneratedSqlWithParams(sql=sql, params=params)


def _to_json_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "isoformat"):  # datetime/date
        return value.isoformat()
    return value
