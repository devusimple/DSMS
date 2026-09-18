"""Pure SQL generation. No engine/connection imports — this module only
turns structured table/column/row descriptions into SQL strings.

DML helpers return ``(statement, params)`` pairs where values are always
bound parameters so generated SQL can be executed safely via
``sqlalchemy.text``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TYPE_RE = re.compile(r"^[A-Za-z0-9_]+(\(\s*\d+\s*\))?$")

#: Portable column types offered by the UI. Extend as needed; keep them
#: valid on SQLite, PostgreSQL, and MySQL.
PORTABLE_TYPES = [
    "INTEGER",
    "TEXT",
    "VARCHAR",
    "BOOLEAN",
    "NUMERIC",
    "REAL",
    "DATE",
    "DATETIME",
]


@dataclass
class ColumnSpec:
    name: str
    data_type: str
    primary_key: bool = False
    nullable: bool = True
    unique: bool = False
    default: str | None = None


@dataclass
class TableSpec:
    name: str
    columns: list[ColumnSpec] = field(default_factory=list)


def quote_ident(name: str, dialect: str = "sqlite") -> str:
    """Quote a single identifier for the given dialect.

    sqlite/postgresql use double quotes, mysql uses backticks.
    """
    validate_ident(name)
    if dialect == "mysql":
        return f"`{name}`"
    return f'"{name}"'


def validate_ident(name: str) -> None:
    if not _IDENT_RE.match(name):
        raise ValueError(
            f"Invalid identifier {name!r}: only letters, digits and "
            "underscores are allowed (must not start with a digit)."
        )


def validate_type(data_type: str) -> None:
    if not _TYPE_RE.match(data_type):
        raise ValueError(f"Invalid column type {data_type!r}.")


def _column_sql(col: ColumnSpec, dialect: str) -> str:
    validate_ident(col.name)
    validate_type(col.data_type)
    parts = [quote_ident(col.name, dialect), col.data_type.upper()]
    parts.append("PRIMARY KEY" if col.primary_key else "NOT NULL" if not col.nullable else "")
    if col.unique:
        parts.append("UNIQUE")
    if col.default is not None:
        parts.append(f"DEFAULT {col.default}")
    return " ".join(p for p in parts if p)


def create_table_sql(table: TableSpec, dialect: str = "sqlite") -> str:
    if not table.columns:
        raise ValueError("A table must have at least one column.")
    body = ",\n    ".join(_column_sql(c, dialect) for c in table.columns)
    return (
        f"CREATE TABLE {quote_ident(table.name, dialect)} (\n"
        f"    {body}\n);"
    )


def drop_table_sql(table_name: str, dialect: str = "sqlite") -> str:
    return f"DROP TABLE {quote_ident(table_name, dialect)};"


def add_column_sql(table_name: str, col: ColumnSpec, dialect: str = "sqlite") -> str:
    return (
        f"ALTER TABLE {quote_ident(table_name, dialect)} "
        f"ADD COLUMN {_column_sql(col, dialect)};"
    )


def drop_column_sql(table_name: str, column_name: str, dialect: str = "sqlite") -> str:
    return (
        f"ALTER TABLE {quote_ident(table_name, dialect)} "
        f"DROP COLUMN {quote_ident(column_name, dialect)};"
    )


def insert_row_sql(
    table_name: str, data: dict[str, object], dialect: str = "sqlite"
) -> tuple[str, dict[str, object]]:
    if not data:
        raise ValueError("Insert requires at least one column value.")
    cols = [quote_ident(k, dialect) for k in data]
    params = {f"__c{i}": v for i, k in enumerate(data) for v in [data[k]]}
    placeholders = list(params)
    sql = (
        f"INSERT INTO {quote_ident(table_name, dialect)} "
        f"({', '.join(cols)}) VALUES ({', '.join(':' + p for p in placeholders)});"
    )
    return sql, params


def update_row_sql(
    table_name: str,
    data: dict[str, object],
    pk: dict[str, object],
    dialect: str = "sqlite",
) -> tuple[str, dict[str, object]]:
    if not data:
        raise ValueError("Update requires at least one column value.")
    if not pk:
        raise ValueError("Update requires a primary key.")
    params: dict[str, object] = {}
    sets = []
    for k, v in data.items():
        param = f"__v{len(params)}"
        sets.append(f"{quote_ident(k, dialect)} = :{param}")
        params[param] = v
    wheres = []
    for k, v in pk.items():
        param = f"__w{len(params)}"
        wheres.append(f"{quote_ident(k, dialect)} = :{param}")
        params[param] = v
    sql = (
        f"UPDATE {quote_ident(table_name, dialect)} SET "
        f"{', '.join(sets)} WHERE {' AND '.join(wheres)};"
    )
    return sql, params


def delete_row_sql(
    table_name: str, pk: dict[str, object], dialect: str = "sqlite"
) -> tuple[str, dict[str, object]]:
    if not pk:
        raise ValueError("Delete requires a primary key.")
    params: dict[str, object] = {}
    wheres = []
    for k, v in pk.items():
        param = f"__w{len(params)}"
        wheres.append(f"{quote_ident(k, dialect)} = :{param}")
        params[param] = v
    sql = (
        f"DELETE FROM {quote_ident(table_name, dialect)} "
        f"WHERE {' AND '.join(wheres)};"
    )
    return sql, params