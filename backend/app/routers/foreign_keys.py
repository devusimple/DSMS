"""Foreign-key relationship reflection and DDL endpoints.

PostgreSQL/MySQL add and drop foreign keys with ``ALTER TABLE``. SQLite has no
``ALTER`` support for constraints, so the router recreates the table (copy →
drop → rename) via ``sqlgen.rebuild_table_sql`` there.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import inspect, text

from app.db import ops
from app.db.manager import ConnectionRecord
from app.routers.deps import get_connection
from app.schemas import ForeignKeyCreate, TableRelationships
from app.sqlgen import (
    ColumnSpec,
    ForeignKeySpec,
    IndexSpec,
    create_foreign_key_sql,
    drop_foreign_key_sql,
    rebuild_table_sql,
    validate_ident,
)

router = APIRouter()


@router.get(
    "/connections/{conn_id}/tables/{table_name}/relationships",
    response_model=TableRelationships,
)
def relationships(
    conn_id: str,
    table_name: str,
    record: ConnectionRecord = Depends(get_connection),
):
    _ensure_table(record, table_name)
    return ops.get_relationships(record, table_name)


@router.post(
    "/connections/{conn_id}/tables/{table_name}/foreign_keys", status_code=201
)
def create_foreign_key(
    conn_id: str,
    table_name: str,
    payload: ForeignKeyCreate,
    record: ConnectionRecord = Depends(get_connection),
):
    _ensure_table(record, table_name)
    _validate(payload)
    name = payload.name or f"fk_{table_name}_{payload.referred_table}_{'_'.join(payload.columns)}"
    new_fk = ForeignKeySpec(
        name=name,
        columns=payload.columns,
        referred_table=payload.referred_table,
        referred_columns=payload.referred_columns,
        on_delete=payload.on_delete,
        on_update=payload.on_update,
    )
    try:
        if record.dialect == "sqlite":
            existing = _reflect_fk_specs(record, table_name)
            _run_fk_change(record, table_name, existing + [new_fk])
        else:
            _run_fk_change(record, table_name, [new_fk])
    except Exception as exc:  # noqa: BLE001 - surface driver errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.delete(
    "/connections/{conn_id}/tables/{table_name}/foreign_keys/{fk_name}",
    status_code=204,
)
def drop_foreign_key(
    conn_id: str,
    table_name: str,
    fk_name: str,
    record: ConnectionRecord = Depends(get_connection),
) -> Response:
    _ensure_table(record, table_name)
    if not fk_name:
        raise HTTPException(status_code=404, detail="Foreign key name is required.")
    if record.dialect == "sqlite":
        current = _reflect_fk_specs(record, table_name)
        remaining = [s for s in current if _spec_name(s, table_name) != fk_name]
        if len(remaining) == len(current):
            raise HTTPException(status_code=404, detail=f"Foreign key {fk_name!r} not found.")
        try:
            _run_fk_change(record, table_name, remaining)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response(status_code=204)

    try:
        with record.engine.begin() as conn:
            conn.execute(text(drop_foreign_key_sql(table_name, fk_name, record.dialect)))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


def _ensure_table(record: ConnectionRecord, table_name: str) -> None:
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")


def _validate(payload: ForeignKeyCreate) -> None:
    validate_ident(payload.referred_table)
    if len(payload.columns) != len(payload.referred_columns):
        raise HTTPException(
            status_code=400,
            detail="columns and referred_columns must have the same length.",
        )
    if payload.name:
        validate_ident(payload.name)


def _spec_name(spec: ForeignKeySpec, table_name: str) -> str:
    if spec.name:
        return spec.name
    return f"fk_{table_name}_{spec.referred_table}_{'_'.join(spec.columns)}"


def _reflect_fk_specs(record: ConnectionRecord, table_name: str) -> list[ForeignKeySpec]:
    """Reflect existing FKs as specs (used for the SQLite rebuild path)."""
    table = ops.reflect_table(record, table_name)
    specs = []
    for fk in table.foreign_key_constraints:
        columns = [c.name for c in fk.columns]
        referred_columns = [e.column.name for e in fk.elements]
        name = fk.name or f"fk_{table_name}_{fk.referred_table.name}_{'_'.join(columns)}"
        specs.append(
            ForeignKeySpec(
                name=name,
                columns=columns,
                referred_table=fk.referred_table.name,
                referred_columns=referred_columns,
                on_delete=fk.ondelete or "",
                on_update=fk.onupdate or "",
            )
        )
    return specs


def _rebuild_columns(record: ConnectionRecord, table_name: str) -> list[ColumnSpec]:
    insp = inspect(record.engine)
    pk_set = set(insp.get_pk_constraint(table_name).get("constrained_columns") or [])
    inline_unique: set[str] = set()
    for constraint in insp.get_unique_constraints(table_name):
        names = constraint.get("column_names") or []
        if len(names) == 1:
            inline_unique.update(names)
    columns = []
    for col in insp.get_columns(table_name):
        default = col.get("default")
        if default is not None:
            default = str(default)
        is_pk = col["name"] in pk_set
        columns.append(
            ColumnSpec(
                name=col["name"],
                data_type=str(col["type"]),
                primary_key=is_pk,
                nullable=bool(col.get("nullable", True)) and not is_pk,
                unique=col["name"] in inline_unique,
                default=default,
            )
        )
    return columns


def _rebuild_indexes(record: ConnectionRecord, table_name: str) -> list[IndexSpec]:
    indexes = []
    for index in ops.list_indexes(record, table_name):
        if index["name"].startswith("sqlite_autoindex_"):
            continue
        indexes.append(
            IndexSpec(
                name=index["name"],
                columns=index["columns"],
                unique=index["unique"],
            )
        )
    return indexes


def _run_fk_change(record: ConnectionRecord, table_name: str, foreign_keys: list[ForeignKeySpec]) -> None:
    """Apply a FK change. ``postgresql``/``mysql`` use ``ALTER``; ``sqlite``
    rebuilds the table."""
    if record.dialect != "sqlite":
        if not foreign_keys:
            return
        fk = foreign_keys[0]
        with record.engine.begin() as conn:
            conn.execute(
                text(
                    create_foreign_key_sql(
                        table_name,
                        fk.name,
                        fk.columns,
                        fk.referred_table,
                        fk.referred_columns,
                        fk.on_delete,
                        fk.on_update,
                        record.dialect,
                    )
                )
            )
        return

    statements = rebuild_table_sql(
        table_name,
        _rebuild_columns(record, table_name),
        foreign_keys,
        _rebuild_indexes(record, table_name),
        record.dialect,
    )
    with record.engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))