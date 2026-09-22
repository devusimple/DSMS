"""Column-level DDL endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from api.db import ops
from api.db.manager import ConnectionRecord
from api.routers.deps import get_connection
from api.schemas import ColumnDef, ColumnUpdate
from api.sqlgen import (
    ColumnSpec,
    add_column_sql,
    drop_column_sql,
    modify_column_sql,
    rebuild_table_sql,
    rename_column_sql,
)

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
        raise HTTPException(
            status_code=404, detail=f"Table {table_name!r} does not exist."
        )
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
        raise HTTPException(
            status_code=404, detail=f"Table {table_name!r} does not exist."
        )
    try:
        with record.engine.begin() as conn:
            conn.execute(text(drop_column_sql(table_name, column_name, record.dialect)))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.patch("/connections/{conn_id}/tables/{table_name}/columns/{column_name}")
def update_column(
    conn_id: str,
    table_name: str,
    column_name: str,
    payload: ColumnUpdate,
    record: ConnectionRecord = Depends(get_connection),
):
    """Rename a column and/or change its type, nullability, or default.

    Primary-key/unique membership cannot be changed here (reflection keeps
    whatever the column already has). SQLite applies definition changes by
    rebuilding the table; renames always use native ``RENAME COLUMN`` so
    foreign keys in other tables follow along.
    """
    if not ops.table_exists(record, table_name):
        raise HTTPException(
            status_code=404, detail=f"Table {table_name!r} does not exist."
        )
    columns = ops.reflect_columns(record, table_name)
    current = next((c for c in columns if c.name == column_name), None)
    if current is None:
        raise HTTPException(
            status_code=404, detail=f"Column {column_name!r} does not exist."
        )

    target = ColumnSpec(
        name=payload.name or current.name,
        data_type=payload.data_type or current.data_type,
        primary_key=current.primary_key,
        nullable=current.nullable if payload.nullable is None else payload.nullable,
        unique=current.unique,
        default=(
            None
            if payload.clear_default
            else (current.default if payload.default is None else payload.default)
        ),
    )
    renamed = target.name != current.name
    if renamed and any(c.name == target.name for c in columns):
        raise HTTPException(
            status_code=409, detail=f"Column {target.name!r} already exists."
        )
    definition_changed = (
        target.data_type.upper() != current.data_type.upper()
        or target.nullable != current.nullable
        or (target.default or None) != (current.default or None)
    )
    if not renamed and not definition_changed:
        return {"ok": True}

    try:
        if renamed:
            with record.engine.begin() as conn:
                conn.execute(
                    text(
                        rename_column_sql(
                            table_name, column_name, target.name, record.dialect
                        )
                    )
                )
        if definition_changed:
            _apply_definition_change(record, table_name, target)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface driver errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


def _apply_definition_change(record, table_name: str, target: ColumnSpec) -> None:
    """Change type/nullability/default of ``target`` in place.

    PostgreSQL/MySQL use ALTER; SQLite rebuilds the table (the rename, if
    any, has already been applied natively so the mapping is identity).
    """
    dialect = record.dialect
    if dialect != "sqlite":
        with record.engine.begin() as conn:
            for statement in modify_column_sql(table_name, target, dialect):
                conn.execute(text(statement))
        return

    columns = [
        target if c.name == target.name else c
        for c in ops.reflect_columns(record, table_name)
    ]
    statements = rebuild_table_sql(
        table_name,
        columns,
        ops.reflect_fks(record, table_name),
        ops.reflect_indexes(record, table_name),
        dialect,
    )
    with record.engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
