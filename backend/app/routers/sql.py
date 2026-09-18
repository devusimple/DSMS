"""Arbitrary SQL execution against a live connection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.db.manager import ConnectionRecord
from app.routers.deps import get_connection
from app.schemas import SqlResult, SqlRun

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
    rows = [
        [_to_json_value(value) for value in row] for row in result.fetchall()
    ]
    return SqlResult(columns=columns, rows=rows, rowcount=result.rowcount or len(rows))


def _to_json_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "isoformat"):  # datetime/date
        return value.isoformat()
    return value
