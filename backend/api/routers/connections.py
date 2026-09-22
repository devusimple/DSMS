"""Connection lifecycle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from api.db.manager import ConnectionFailed, ConnectionRecord, manager
from api.routers.deps import get_connection
from api.schemas import ConnectionCreate, ConnectionOut

router = APIRouter()


def _to_out(rec: ConnectionRecord) -> ConnectionOut:
    return ConnectionOut(
        id=rec.id, name=rec.name, dialect=rec.dialect, url=rec.url_display
    )


@router.post("/connections", response_model=ConnectionOut, status_code=201)
def create_connection(payload: ConnectionCreate) -> ConnectionOut:
    from api.db.manager import ConnectionSpec

    spec = ConnectionSpec(**payload.model_dump(exclude_unset=True))
    try:
        record = manager.create(spec)
    except ConnectionFailed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_out(record)


@router.get("/connections", response_model=list[ConnectionOut])
def list_connections() -> list[ConnectionOut]:
    return [_to_out(rec) for rec in manager.list()]


@router.delete("/connections/{conn_id}", status_code=204)
def delete_connection(conn_id: str) -> Response:
    if not manager.close(conn_id):
        raise HTTPException(
            status_code=404, detail=f"Unknown connection id {conn_id!r}"
        )
    return Response(status_code=204)


@router.post("/connections/{conn_id}/test", response_model=ConnectionOut)
def test_connection(conn_id: str) -> ConnectionOut:
    return _to_out(get_connection(conn_id))
