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
    exclude_auto: list[str] = Field(default_factory=list)


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
    total: int = 0


# ------------------------------------------------------------------- columns
class ColumnUpdate(BaseModel):
    """Partial column change. ``None`` means "unchanged"; ``clear_default``
    removes a default (a bare ``default=None`` is ambiguous)."""

    name: str | None = None
    data_type: str | None = None
    nullable: bool | None = None
    default: str | None = None
    clear_default: bool = False


class SqlResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    rowcount: int


# -------------------------------------------------------------------- indexes
class IndexInfo(BaseModel):
    name: str
    columns: list[str]
    unique: bool


class IndexCreate(BaseModel):
    name: str
    columns: list[str] = Field(min_length=1)
    unique: bool = False


# ------------------------------------------------------------- foreign keys
class ForeignKeyCreate(BaseModel):
    name: str | None = None
    columns: list[str] = Field(min_length=1)
    referred_table: str
    referred_columns: list[str] = Field(min_length=1)
    on_delete: Literal["", "NO ACTION", "RESTRICT", "CASCADE", "SET NULL", "SET DEFAULT"] = ""
    on_update: Literal["", "NO ACTION", "RESTRICT", "CASCADE", "SET NULL", "SET DEFAULT"] = ""


class ForeignKeyInfo(BaseModel):
    name: str
    columns: list[str]
    referred_table: str
    referred_columns: list[str]
    on_delete: str
    on_update: str
    cardinality: Literal["1:1", "1:N", "N:1"]


class ReferencingForeignKeyInfo(BaseModel):
    table: str
    name: str
    columns: list[str]
    referred_columns: list[str]
    on_delete: str
    on_update: str
    cardinality: Literal["1:1", "1:N", "N:1"]


class ManyToManyInfo(BaseModel):
    endpoint: str
    through: str


class TableRelationships(BaseModel):
    junction: bool
    outbound: list[ForeignKeyInfo]
    inbound: list[ReferencingForeignKeyInfo]
    many_to_many: list[ManyToManyInfo]


# ---------------------------------------------------------------- sql generate
class GenerateSql(BaseModel):
    """Structured request to build a SQL statement from options.

    `verb` selects the generator; unused fields are ignored.
    """

    table: str
    verb: Literal["select", "count", "insert", "update", "delete", "upsert"] = "select"
    # select / count options
    columns: list[str] | None = None
    eq: dict[str, Any] | None = None
    where: list[tuple[str, str, Any]] | None = None
    search: str | None = None
    search_columns: list[str] | None = None
    distinct: bool = False
    order_by: str | list[str] | None = None
    order_dir: str = "asc"
    limit: int | None = None
    offset: int | None = None
    page: int | None = None
    page_size: int | None = None
    # dml options
    data: dict[str, Any] | None = None
    pk: dict[str, Any] | None = None
    conflict_columns: list[str] | None = None


class GeneratedSqlWithParams(BaseModel):
    sql: str
    params: dict[str, Any] = Field(default_factory=dict)


# -------------------------------------------------------------------------- sql
class SqlRun(BaseModel):
    statement: str
    params: dict[str, Any] | list[Any] | None = None


class GeneratedSql(BaseModel):
    sql: str


# ----------------------------------------------------------------------- diff
class DiffRequest(BaseModel):
    """Diff request: make ``source_conn_id``'s schema the desired state and
    the endpoint's connection the one being migrated."""

    source_conn_id: str
    include_drops: bool = False


class DiffEntryOut(BaseModel):
    kind: str
    table: str
    column: str | None = None
    detail: str = ""
    sql: list[str] = Field(default_factory=list)


class DiffOut(BaseModel):
    dialect: Dialect
    entries: list[DiffEntryOut]
    sql: str


# ------------------------------------------------------------- import/export
class ImportRequest(BaseModel):
    csv: str = Field(min_length=1)
    has_header: bool = True
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    dry_run: bool = False


class ImportPreview(BaseModel):
    columns: list[str]
    total_rows: int
    sample: list[dict[str, Any]] = Field(default_factory=list)


class ImportResult(BaseModel):
    inserted: int