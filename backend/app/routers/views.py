"""Read-only view endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.db import ops
from app.routers.deps import get_connection
from app.schemas import RowsOut

router = APIRouter()


@router.get("/connections/{conn_id}/views")
def list_views(
    conn_id: str,
    record: ConnectionRecord = Depends(get_connection),
):
    return ops.list_views(record)


@router.get("/connections/{conn_id}/views/{view_name}/rows")
def view_rows(
    conn_id: str,
    view_name: str,
    limit: int = 1000,
    record: ConnectionRecord = Depends(get_connection),
):
    if view_name not in ops.list_views(record):
        return RowsOut(columns=[], rows=[])
    columns, rows = ops.fetch_view_rows(record, view_name, limit)
    return RowsOut(columns=columns, rows=[dict(zip(columns, row)) for row in rows])