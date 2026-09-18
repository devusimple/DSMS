"""Reflection helpers layered on top of the connection manager.

All database reads/writes flow through SQLAlchemy (Core). Table/row
operations reflect the live schema, so tables created outside DSMS are
handled correctly too.
"""

from __future__ import annotations

from sqlalchemy import MetaData, Table, inspect

from app.db.manager import ConnectionRecord


def table_exists(record: ConnectionRecord, table_name: str) -> bool:
    return table_name in inspect(record.engine).get_table_names()


def reflect_table(record: ConnectionRecord, table_name: str) -> Table:
    if not table_exists(record, table_name):
        raise KeyError(f"Table {table_name!r} does not exist.")
    return Table(table_name, MetaData(), autoload_with=record.engine)


def list_tables(record: ConnectionRecord) -> list[dict]:
    """Return the schema as [{name, columns: [{name, data_type, ...}]}]."""
    insp = inspect(record.engine)
    out: list[dict] = []
    for table_name in insp.get_table_names():
        pk_columns = set(insp.get_pk_constraint(table_name).get("constrained_columns") or [])
        unique_columns = _unique_columns(insp, table_name)
        columns = []
        for col in insp.get_columns(table_name):
            default = col.get("default")
            if default is not None:
                default = str(default)
            is_pk = col["name"] in pk_columns
            columns.append(
                {
                    "name": col["name"],
                    "data_type": str(col["type"]),
                    "primary_key": is_pk,
                    "nullable": bool(col.get("nullable", True)) and not is_pk,
                    "unique": col["name"] in unique_columns,
                    "default": default,
                }
            )
        out.append({"name": table_name, "columns": columns})
    return out


def _unique_columns(insp, table_name: str) -> set[str]:
    cols: set[str] = set()
    for constraint in insp.get_unique_constraints(table_name):
        cols.update(constraint.get("column_names") or [])
    return cols


def primary_key(record: ConnectionRecord, table_name: str) -> list[str]:
    insp = inspect(record.engine)
    return list(insp.get_pk_constraint(table_name).get("constrained_columns") or [])


def fetch_rows(record: ConnectionRecord, table_name: str):
    """Yield (column_names, rows) for a table."""
    table = reflect_table(record, table_name)
    column_names = [c.name for c in table.columns]
    with record.engine.connect() as conn:
        result = conn.execute(table.select())
        rows = [dict(row) for row in result.mappings()]
    return column_names, rows