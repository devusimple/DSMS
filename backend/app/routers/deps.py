"""Shared router dependencies."""

from __future__ import annotations

from fastapi import HTTPException

from app.db.manager import ConnectionRecord, manager


def get_connection(conn_id: str) -> ConnectionRecord:
    try:
        return manager.get(conn_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
