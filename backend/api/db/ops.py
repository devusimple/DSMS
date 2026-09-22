"""Reflection helpers layered on top of the connection manager.

All database reads/writes flow through SQLAlchemy (Core). Table/row
operations reflect the live schema, so tables created outside DSMS are
handled correctly too.
"""

from __future__ import annotations

from sqlalchemy import MetaData, Table, inspect, text

from api.db.manager import ConnectionRecord
from api.schemadiff import TableSnapshot
from api.sqlgen import (
    ColumnSpec,
    ForeignKeySpec,
    IndexSpec,
    quote_ident,
)


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
        pk_columns = set(
            insp.get_pk_constraint(table_name).get("constrained_columns") or []
        )
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


def list_indexes(record: ConnectionRecord, table_name: str) -> list[dict]:
    insp = inspect(record.engine)
    indexes = []
    for index in insp.get_indexes(table_name):
        indexes.append(
            {
                "name": index["name"],
                "columns": list(index.get("column_names") or []),
                "unique": bool(index.get("unique")),
            }
        )
    return indexes


def list_views(record: ConnectionRecord) -> list[str]:
    insp = inspect(record.engine)
    try:
        return list(insp.get_view_names())
    except NotImplementedError:
        return []


def fetch_view_rows(record: ConnectionRecord, view_name: str, limit: int = 1000):
    """Read-only select from a view (no reflection required)."""
    statement = (
        f"SELECT * FROM {quote_ident(view_name, record.dialect)} LIMIT {int(limit)}"
    )
    with record.engine.connect() as conn:
        result = conn.execute(text(statement))
        column_names = list(result.keys())
        rows = [list(row) for row in result.fetchall()]
    return column_names, rows


def fetch_rows(record: ConnectionRecord, table_name: str):
    """Yield (column_names, rows) for a table."""
    table = reflect_table(record, table_name)
    column_names = [c.name for c in table.columns]
    with record.engine.connect() as conn:
        result = conn.execute(table.select())
        rows = [dict(row) for row in result.mappings()]
    return column_names, rows


# ------------------------------------------------------------------ foreign keys
def fk_name(fk, table_name: str) -> str:
    """Deterministic name for a reflected FK constraint.

    SQLite often leaves FK constraints unnamed; fall back to a stable
    generated name so the UI and drop-by-name both work.
    """
    if fk.name:
        return fk.name
    local = [c.name for c in fk.columns]
    return f"fk_{table_name}_{fk.referred_table.name}_{'_'.join(local)}"


def reflect_columns(record: ConnectionRecord, table_name: str) -> list[ColumnSpec]:
    """Reflect a table's columns as ColumnSpecs (inline single-column unique
    flags only; composite uniques surface as indexes instead)."""
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


def reflect_indexes(record: ConnectionRecord, table_name: str) -> list[IndexSpec]:
    """Reflect a table's indexes, skipping engine-owned ones (sqlite_autoindex)."""
    indexes = []
    for index in list_indexes(record, table_name):
        if index["name"].startswith("sqlite_autoindex_"):
            continue
        indexes.append(
            IndexSpec(
                name=index["name"],
                columns=list(index["columns"]),
                unique=index["unique"],
            )
        )
    return indexes


def reflect_fks(record: ConnectionRecord, table_name: str) -> list[ForeignKeySpec]:
    """Reflect a table's foreign keys as specs (unnamed ones get the stable
    ``fk_<table>_<parent>_<cols>`` name)."""
    table = reflect_table(record, table_name)
    specs = []
    for fk in table.foreign_key_constraints:
        columns = [c.name for c in fk.columns]
        specs.append(
            ForeignKeySpec(
                name=fk_name(fk, table_name),
                columns=columns,
                referred_table=fk.referred_table.name,
                referred_columns=[e.column.name for e in fk.elements],
                on_delete=fk.ondelete or "",
                on_update=fk.onupdate or "",
            )
        )
    return specs


def snapshot_schema(record: ConnectionRecord) -> list[TableSnapshot]:
    """Full schema snapshot (tables with columns/indexes/FKs; views excluded)."""
    snapshots = []
    for table_name in inspect(record.engine).get_table_names():
        snapshots.append(
            TableSnapshot(
                name=table_name,
                columns=reflect_columns(record, table_name),
                indexes=reflect_indexes(record, table_name),
                foreign_keys=reflect_fks(record, table_name),
            )
        )
    return snapshots


def _pk_set(insp, table_name: str) -> set[str]:
    return set(insp.get_pk_constraint(table_name).get("constrained_columns") or [])


def _fk_cardinality(local: list[str], primary_key: set[str]) -> str:
    """Cardinality from the *referencing* table's perspective.

    ``1:1`` when the FK covers the whole primary key, otherwise ``1:N``.
    """
    return "1:1" if local and set(local) == primary_key else "1:N"


def list_foreign_keys(record: ConnectionRecord, table_name: str) -> list[dict]:
    """Foreign keys defined *on* ``table`` (outbound references)."""
    table = reflect_table(record, table_name)
    insp = inspect(record.engine)
    own_pk = _pk_set(insp, table_name)
    outbound = []
    for fk in table.foreign_key_constraints:
        local = [c.name for c in fk.columns]
        # Outbound reading: "this table -> parent". Many rows per one parent
        # unless the FK covers this table's whole primary key (1:1).
        cardinality = "1:1" if local and set(local) == own_pk else "N:1"
        outbound.append(
            {
                "name": fk_name(fk, table_name),
                "columns": local,
                "referred_table": fk.referred_table.name,
                "referred_columns": [e.column.name for e in fk.elements],
                "on_delete": fk.ondelete or "",
                "on_update": fk.onupdate or "",
                "cardinality": cardinality,
            }
        )
    return outbound


def _junction_references(insp, table) -> list[str] | None:
    """If ``table`` is a pure junction table, return its two endpoint names.

    A junction connects two other tables via exactly two FKs whose columns
    together form its primary key. Returns ``None`` otherwise.
    """
    fks = list(table.foreign_key_constraints)
    if len(fks) != 2:
        return None
    union: set[str] = set()
    for fk in fks:
        union.update(c.name for c in fk.columns)
    if not fks or union != _pk_set(insp, table.name):
        return None
    endpoints = {fk.referred_table.name for fk in fks}
    if len(endpoints) != 2:
        return None
    return sorted(endpoints)


def get_relationships(record: ConnectionRecord, table_name: str) -> dict:
    """Full relationship picture for a table: outbound, inbound, and any
    many-to-many routes the table participates in."""
    table = reflect_table(record, table_name)
    insp = inspect(record.engine)
    outbound = list_foreign_keys(record, table_name)

    metadata = MetaData()
    metadata.reflect(record.engine)
    inbound = []
    for other in metadata.tables.values():
        if other.name == table_name:
            continue
        child_pk = _pk_set(insp, other.name)
        for fk in other.foreign_key_constraints:
            if fk.referred_table.name != table_name:
                continue
            local = [c.name for c in fk.columns]
            inbound.append(
                {
                    "table": other.name,
                    "name": fk_name(fk, other.name),
                    "columns": local,
                    "referred_columns": [e.column.name for e in fk.elements],
                    "on_delete": fk.ondelete or "",
                    "on_update": fk.onupdate or "",
                    "cardinality": _fk_cardinality(local, child_pk),
                }
            )

    junction = _junction_references(insp, table)
    many_to_many = []
    if junction:
        for endpoint in junction:
            many_to_many.append({"endpoint": endpoint, "through": table_name})
    else:
        for other in metadata.tables.values():
            endpoints = _junction_references(insp, other)
            if endpoints and table_name in endpoints:
                endpoint = next(n for n in endpoints if n != table_name)
                many_to_many.append({"endpoint": endpoint, "through": other.name})

    return {
        "junction": junction is not None,
        "outbound": outbound,
        "inbound": inbound,
        "many_to_many": many_to_many,
    }
