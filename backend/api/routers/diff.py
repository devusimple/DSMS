"""Schema diff endpoint: compare two live connections and generate the SQL
that migrates this connection towards the source connection's schema."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.db import ops
from api.db.manager import ConnectionRecord, manager
from api.routers.deps import get_connection
from api.schemadiff import diff_schemas, migration_script
from api.schemas import DiffEntryOut, DiffOut, DiffRequest

router = APIRouter()


@router.post("/connections/{conn_id}/diff", response_model=DiffOut)
def diff_connection(
    conn_id: str,
    payload: DiffRequest,
    record: ConnectionRecord = Depends(get_connection),
) -> DiffOut:
    """Diff ``payload.source_conn_id`` (desired) against this connection.

    The response lists every change plus a ready-to-review SQL script for
    this connection's dialect. Cross-dialect diffs are allowed for review,
    but generated types may need manual adjustment.
    """
    try:
        source_record = manager.get(payload.source_conn_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source connection {payload.source_conn_id!r}.",
        ) from exc

    try:
        source = ops.snapshot_schema(source_record)
        target = ops.snapshot_schema(record)
        entries = diff_schemas(source, target, record.dialect, payload.include_drops)
    except Exception as exc:  # noqa: BLE001 - surface driver errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DiffOut(
        dialect=record.dialect,
        entries=[
            DiffEntryOut(
                kind=e.kind, table=e.table, column=e.column, detail=e.detail, sql=e.sql
            )
            for e in entries
        ],
        sql=migration_script(entries, record.dialect),
    )
