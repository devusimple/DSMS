"""Column-level DDL endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.db import ops
from app.routers.deps import get_connection
from app.schemas import ColumnDef
from app.sqlgen import ColumnSpec, add_column_sql, drop_column_sql

router = APIRouter()


@router.post(
    "/connections/{conn_id}/tables/{table_name}/columns",
    status_code=201,
)
def add_column(
    conn_id: str,
    table_name: str,
    payload: ColumnDef,
    record: ConnectionRecord = Depends(get_connection),
):
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
    col = ColumnSpec(
        name=payload.name,
        data_type=payload.data_type,
        primary_key=payload.primary_key,
        nullable=payload.nullable,
        unique=payload.unique,
        default=payload.default,
    )
    try:
        with record.engine.begin() as conn:
            conn.execute(text(add_column_sql(table_name, col, record.dialect)))
    except Exception as exc:  # noqa: BLE001 - surface driver errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.delete("/connections/{conn_id}/tables/{table_name}/columns/{column_name}")
def drop_column(
    conn_id: str,
    table_name: str,
    column_name: str,
    record: ConnectionRecord = Depends(get_connection),
):
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
    try:
        with record.engine.begin() as conn:
            conn.execute(text(drop_column_sql(table_name, column_name, record.dialect)))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}
