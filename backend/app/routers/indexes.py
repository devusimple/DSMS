"""Index-level DDL endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.db import ops
from app.routers.deps import get_connection
from app.schemas import IndexCreate
from app.sqlgen import create_index_sql, drop_index_sql

router = APIRouter()


@router.get("/connections/{conn_id}/tables/{table_name}/indexes")
def list_indexes(
    conn_id: str,
    table_name: str,
    record: ConnectionRecord = Depends(get_connection),
):
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
    return ops.list_indexes(record, table_name)


@router.post("/connections/{conn_id}/tables/{table_name}/indexes", status_code=201)
def create_index(
    conn_id: str,
    table_name: str,
    payload: IndexCreate,
    record: ConnectionRecord = Depends(get_connection),
):
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
    try:
        with record.engine.begin() as conn:
            conn.execute(text(create_index_sql(table_name, payload.name, payload.columns, payload.unique, record.dialect)))
    except Exception as exc:  # noqa: BLE001 - surface driver errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.delete("/connections/{conn_id}/tables/{table_name}/indexes/{index_name}", status_code=204)
def drop_index(
    conn_id: str,
    table_name: str,
    index_name: str,
    record: ConnectionRecord = Depends(get_connection),
):
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
    try:
        with record.engine.begin() as conn:
            conn.execute(text(drop_index_sql(table_name, index_name, record.dialect)))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}