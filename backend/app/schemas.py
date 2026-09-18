"""Pydantic request/response schemas for the DSMS API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Dialect = Literal["sqlite", "postgresql", "mysql"]


# ---------------------------------------------------------------- connections
class ConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    dialect: Dialect
    # Full DSN takes precedence when provided (e.g. "postgresql://user:pw@host/db").
    dsn: str | None = None
    # Component form (used when dsn is absent).
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    # sqlite only: path to a file, or ":memory:" / omit for an in-memory db.
    file: str | None = None


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    dialect: Dialect
    url: str


# ------------------------------------------------------------------ table DDL
class ColumnDef(BaseModel):
    name: str
    data_type: str
    primary_key: bool = False
    nullable: bool = True
    unique: bool = False
    default: str | None = None


class TableCreate(BaseModel):
    name: str
    columns: list[ColumnDef] = Field(min_length=1)


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    primary_key: bool
    nullable: bool
    unique: bool
    default: str | None = None


class TableInfo(BaseModel):
    name: str
    columns: list[ColumnInfo]


# ----------------------------------------------------------------------- rows
class RowAction(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    pk: dict[str, Any] | None = None


class RowsOut(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]


class SqlResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    rowcount: int


# -------------------------------------------------------------------------- sql
class SqlRun(BaseModel):
    statement: str
    params: dict[str, Any] | list[Any] | None = None


class GeneratedSql(BaseModel):
    sql: str