"""Table schema management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text

from app.db import ops
from app.routers.deps import get_connection
from app.schemas import ColumnDef, GeneratedSql, TableCreate, TableInfo
from app.sqlgen import ColumnSpec, TableSpec, create_table_sql, drop_table_sql

router = APIRouter()

#: Columns appended to every table unless the user already defined them.
AUTO_COLUMNS = [
    ColumnSpec(name="_id", data_type="INTEGER", primary_key=True, nullable=False),
    ColumnSpec(
        name="created_at",
        data_type="DATETIME",
        nullable=False,
        default="CURRENT_TIMESTAMP",
    ),
    ColumnSpec(
        name="updated_at",
        data_type="DATETIME",
        nullable=False,
        default="CURRENT_TIMESTAMP",
    ),
]


def _with_auto_columns(cols: list[ColumnSpec], exclude: list[str] | None = None) -> list[ColumnSpec]:
    """Ensure `_id`/`created_at`/`updated_at` exist on a new table spec.

    `_id` is added as the surrogate primary key only when the user did not
    define a primary key themselves. Columns already present or listed in
    `exclude` are never added, so callers can opt out individually.
    """
    excluded = set(exclude or [])
    names = {c.name for c in cols}
    if "_id" not in names and "_id" not in excluded and not any(c.primary_key for c in cols):
        cols.insert(0, AUTO_COLUMNS[0])
    if "created_at" not in names and "created_at" not in excluded:
        cols.append(AUTO_COLUMNS[1])
    if "updated_at" not in names and "updated_at" not in excluded:
        cols.append(AUTO_COLUMNS[2])
    return cols


@router.get("/connections/{conn_id}/tables", response_model=list[TableInfo])
def list_tables(conn_id: str, record: ConnectionRecord = Depends(get_connection)):
    return ops.list_tables(record)


@router.post(
    "/connections/{conn_id}/tables", response_model=TableInfo, status_code=201
)
def create_table(
    conn_id: str,
    payload: TableCreate,
    record: ConnectionRecord = Depends(get_connection),
):
    if ops.table_exists(record, payload.name):
        raise HTTPException(status_code=409, detail=f"Table {payload.name!r} already exists.")
    table = TableSpec(
        payload.name,
        _with_auto_columns([_column_spec(c) for c in payload.columns], payload.exclude_auto),
    )
    statement = create_table_sql(table, record.dialect)
    try:
        with record.engine.begin() as conn:
            conn.execute(text(statement))
    except Exception as exc:  # noqa: BLE001 - surface driver errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _table_info(record, payload.name)


@router.delete("/connections/{conn_id}/tables/{table_name}", status_code=204)
def drop_table(
    conn_id: str,
    table_name: str,
    record: ConnectionRecord = Depends(get_connection),
) -> Response:
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
    try:
        with record.engine.begin() as conn:
            conn.execute(text(drop_table_sql(table_name, record.dialect)))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get(
    "/connections/{conn_id}/tables/{table_name}/sql", response_model=GeneratedSql
)
def table_sql(
    conn_id: str,
    table_name: str,
    record: ConnectionRecord = Depends(get_connection),
) -> GeneratedSql:
    if not ops.table_exists(record, table_name):
        raise HTTPException(status_code=404, detail=f"Table {table_name!r} does not exist.")
    table = next(t for t in ops.list_tables(record) if t["name"] == table_name)
    table_spec = TableSpec(
        table_name,
        [
            ColumnSpec(
                name=c["name"],
                data_type=c["data_type"],
                primary_key=c["primary_key"],
                nullable=c["nullable"],
                unique=c["unique"],
                default=c["default"],
            )
            for c in table["columns"]
        ],
    )
    return GeneratedSql(sql=create_table_sql(table_spec, record.dialect))


def _column_spec(col: ColumnDef) -> ColumnSpec:
    return ColumnSpec(
        name=col.name,
        data_type=col.data_type,
        primary_key=col.primary_key,
        nullable=col.nullable,
        unique=col.unique,
        default=col.default,
    )


def _table_info(record: ConnectionRecord, name: str) -> TableInfo:
    return next(t for t in ops.list_tables(record) if t["name"] == name)

