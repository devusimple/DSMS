"""Pure schema diffing: compare two reflected schemas and generate the SQL
that migrates the *target* to match the *source*.

No engine/connection imports — callers pass reflected snapshots
(:class:`TableSnapshot`) in and get :class:`DiffEntry` items out, each carrying
the SQL statements for one change plus a human-readable description. SQL text
is built by :mod:`app.sqlgen` so dialect quoting stays in one place.

Column renames cannot be detected (a rename is indistinguishable from a
drop + add); they are reported as ``drop_column``/``add_column`` pairs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.sqlgen import (
    ColumnSpec,
    ForeignKeySpec,
    IndexSpec,
    TableSpec,
    add_column_sql,
    create_foreign_key_sql,
    create_index_sql,
    create_table_sql,
    drop_column_sql,
    drop_foreign_key_sql,
    drop_index_sql,
    drop_table_sql,
    modify_column_sql,
    rebuild_table_sql,
)


@dataclass
class TableSnapshot:
    """Reflected state of one table: columns, indexes, and foreign keys."""

    name: str
    columns: list[ColumnSpec] = field(default_factory=list)
    indexes: list[IndexSpec] = field(default_factory=list)
    foreign_keys: list[ForeignKeySpec] = field(default_factory=list)


@dataclass
class DiffEntry:
    """One migration step: what changed, where, and the SQL to apply it."""

    kind: str
    table: str
    column: str | None = None
    detail: str = ""
    sql: list[str] = field(default_factory=list)


def _normalize_type(data_type: str) -> str:
    return " ".join(str(data_type).upper().split())


def _column_identity(col: ColumnSpec) -> tuple:
    """Comparable identity of a column definition (name excluded)."""
    return (
        _normalize_type(col.data_type),
        bool(col.primary_key),
        bool(col.nullable),
        str(col.default).strip().upper() if col.default is not None else None,
    )


def _index_identity(index: IndexSpec) -> tuple:
    return (tuple(index.columns), bool(index.unique))


def _fk_identity(fk: ForeignKeySpec) -> tuple:
    return (
        tuple(fk.columns),
        fk.referred_table,
        tuple(fk.referred_columns),
        (fk.on_delete or "").upper(),
        (fk.on_update or "").upper(),
    )


def _topological_order(snapshots: list[TableSnapshot]) -> tuple[list[str], bool]:
    """Order table names so FK parents come before children.

    Returns ``(names, has_cycle)``; a cycle falls back to snapshot order
    (the caller emits a warning comment in the script).
    """
    graph = {s.name: set() for s in snapshots}
    for snap in snapshots:
        for fk in snap.foreign_keys:
            if fk.referred_table in graph and fk.referred_table != snap.name:
                graph[snap.name].add(fk.referred_table)
    ordered: list[str] = []
    visiting: set[str] = set()
    done: set[str] = set()
    has_cycle = False

    def visit(name: str) -> None:
        nonlocal has_cycle
        if name in done:
            return
        if name in visiting:  # cycle — keep snapshot order for the rest
            has_cycle = True
            return
        visiting.add(name)
        for dep in sorted(graph[name]):
            visit(dep)
        visiting.discard(name)
        done.add(name)
        ordered.append(name)

    for snap in snapshots:
        visit(snap.name)
    return ordered, has_cycle


def diff_schemas(
    source: list[TableSnapshot],
    target: list[TableSnapshot],
    dialect: str = "sqlite",
    include_drops: bool = False,
) -> list[DiffEntry]:
    """Diff ``source`` (desired schema) against ``target`` (current schema).

    The returned entries, applied in order, migrate the target towards the
    source. Destructive steps (drop table / drop column) are included only
    when ``include_drops`` is set.
    """
    source_by_name = {s.name: s for s in source}
    target_by_name = {s.name: s for s in target}
    entries: list[DiffEntry] = []

    # ---- new tables (parents first, FKs inline, indexes after) ----
    created = [s for s in source if s.name not in target_by_name]
    if created:
        order, _ = _topological_order(created)
        by_name = {s.name: s for s in created}
        for name in order:
            snap = by_name[name]
            entries.append(
                DiffEntry(
                    kind="create_table",
                    table=name,
                    detail=f"create table {name} ({len(snap.columns)} columns)",
                    sql=[create_table_sql(TableSpec(name, list(snap.columns)), dialect, snap.foreign_keys)]
                    + [
                        create_index_sql(name, idx.name, idx.columns, idx.unique, dialect)
                        for idx in snap.indexes
                    ],
                )
            )

    # ---- tables present on both sides ----
    for snap in target:
        if snap.name not in source_by_name:
            continue
        src = source_by_name[snap.name]
        entries.extend(_diff_table(src, snap, dialect, include_drops))

    # ---- dropped tables (children first) ----
    if include_drops:
        dropped = [s for s in target if s.name not in source_by_name]
        if dropped:
            order, _ = _topological_order(dropped)
            by_name = {s.name: s for s in dropped}
            for name in reversed(order):
                entries.append(
                    DiffEntry(
                        kind="drop_table",
                        table=name,
                        detail=f"drop table {name}",
                        sql=[drop_table_sql(name, dialect)],
                    )
                )
    return entries


def _diff_table(
    src: TableSnapshot, tgt: TableSnapshot, dialect: str, include_drops: bool
) -> list[DiffEntry]:
    entries: list[DiffEntry] = []
    src_cols = {c.name: c for c in src.columns}
    tgt_cols = {c.name: c for c in tgt.columns}

    added = [c for c in src.columns if c.name not in tgt_cols]
    removed = [c for c in tgt.columns if c.name not in src_cols]
    changed = [
        (tgt_cols[c.name], c)
        for c in src.columns
        if c.name in tgt_cols and _column_identity(c) != _column_identity(tgt_cols[c.name])
    ]

    # SQLite cannot ALTER column definitions or FKs in place: fold every
    # definition-level change on this table into one rebuild.
    fk_diff = _fk_changes(src, tgt)
    if dialect == "sqlite" and (changed or fk_diff[0] or fk_diff[1]):
        entries.extend(_sqlite_rebuild_entry(src, tgt, changed, fk_diff, dialect))
    else:
        for old, new in changed:
            entries.append(
                DiffEntry(
                    kind="modify_column",
                    table=tgt.name,
                    column=new.name,
                    detail=_column_change_detail(old, new),
                    sql=modify_column_sql(tgt.name, new, dialect),
                )
            )
        for fk, action in _fk_pairs(fk_diff):
            if action == "add":
                entries.append(
                    DiffEntry(
                        kind="add_foreign_key",
                        table=tgt.name,
                        detail=f"add foreign key {fk.name} -> {fk.referred_table}",
                        sql=[
                            create_foreign_key_sql(
                                tgt.name, fk.name, fk.columns, fk.referred_table,
                                fk.referred_columns, fk.on_delete, fk.on_update, dialect,
                            )
                        ],
                    )
                )
            else:
                entries.append(
                    DiffEntry(
                        kind="drop_foreign_key",
                        table=tgt.name,
                        detail=f"drop foreign key {fk.name}",
                        sql=[drop_foreign_key_sql(tgt.name, fk.name, dialect)],
                    )
                )

    for col in added:
        entries.append(
            DiffEntry(
                kind="add_column",
                table=tgt.name,
                column=col.name,
                detail=f"add column {col.name} {col.data_type}",
                sql=[add_column_sql(tgt.name, col, dialect)],
            )
        )
    if include_drops:
        for col in removed:
            entries.append(
                DiffEntry(
                    kind="drop_column",
                    table=tgt.name,
                    column=col.name,
                    detail=f"drop column {col.name}",
                    sql=[drop_column_sql(tgt.name, col.name, dialect)],
                )
            )

    entries.extend(_diff_indexes(src, tgt, dialect, include_drops))
    return entries


def _fk_changes(src: TableSnapshot, tgt: TableSnapshot) -> tuple[list[ForeignKeySpec], list[ForeignKeySpec]]:
    """FK specs to add / drop to move ``tgt`` to ``src`` (matched by identity,
    not by constraint name — names differ across engines)."""
    def keys(snap: TableSnapshot) -> dict[tuple, ForeignKeySpec]:
        return {_fk_identity(fk): fk for fk in snap.foreign_keys}

    src_keys, tgt_keys = keys(src), keys(tgt)
    to_add = [src_keys[k] for k in src_keys if k not in tgt_keys]
    to_drop = [tgt_keys[k] for k in tgt_keys if k not in src_keys]
    return to_add, to_drop


def _fk_pairs(fk_diff: tuple[list[ForeignKeySpec], list[ForeignKeySpec]]):
    for fk in fk_diff[1]:
        yield fk, "drop"
    for fk in fk_diff[0]:
        yield fk, "add"


def _column_change_detail(old: ColumnSpec, new: ColumnSpec) -> str:
    bits = []
    if _normalize_type(old.data_type) != _normalize_type(new.data_type):
        bits.append(f"{old.data_type} -> {new.data_type}")
    if old.nullable != new.nullable:
        bits.append("null" if new.nullable else "not null")
    if (old.default or None) != (new.default or None):
        bits.append(f"default {new.default!r}" if new.default is not None else "drop default")
    if old.primary_key != new.primary_key:
        bits.append("primary key" if new.primary_key else "drop primary key")
    if old.unique != new.unique:
        bits.append("unique" if new.unique else "drop unique")
    summary = ", ".join(bits)
    return f"change {new.name}: {summary}" if summary else f"change {new.name}"


def _sqlite_rebuild_entry(
    src: TableSnapshot,
    tgt: TableSnapshot,
    changed: list[tuple[ColumnSpec, ColumnSpec]],
    fk_diff: tuple[list[ForeignKeySpec], list[ForeignKeySpec]],
    dialect: str,
) -> list[DiffEntry]:
    """One table-rebuild entry combining changed columns and FK changes.

    The rebuilt column list keeps the source table's column definitions for
    every column both sides know (changed or not); columns only on the target
    are kept as-is (drops stay separate, native ``DROP COLUMN``), columns only
    on the source are handled by the normal ``add_column`` path afterwards.
    """
    src_cols = {c.name: c for c in src.columns}
    columns: list[ColumnSpec] = []
    source_columns: list[str] = []
    for col in tgt.columns:
        if col.name in src_cols:
            columns.append(src_cols[col.name])
        else:
            columns.append(col)
        source_columns.append(col.name)

    add, drop = fk_diff
    drop_identities = {_fk_identity(fk) for fk in drop}
    final_fks = [fk for fk in tgt.foreign_keys if _fk_identity(fk) not in drop_identities]
    existing_identities = {_fk_identity(fk) for fk in final_fks}
    for fk in add:
        if _fk_identity(fk) not in existing_identities:
            final_fks.append(fk)

    details = [_column_change_detail(old, new) for old, new in changed]
    details += [f"add foreign key {fk.name} -> {fk.referred_table}" for fk in add]
    details += [f"drop foreign key {fk.name}" for fk in drop]
    return [
        DiffEntry(
            kind="rebuild_table",
            table=tgt.name,
            detail="; ".join(details),
            sql=rebuild_table_sql(
                tgt.name,
                columns,
                final_fks,
                _rebuildable_indexes(tgt),
                dialect,
                source_columns=source_columns,
            ),
        )
    ]


def _rebuildable_indexes(snap: TableSnapshot) -> list[IndexSpec]:
    return [
        IndexSpec(name=idx.name, columns=list(idx.columns), unique=idx.unique)
        for idx in snap.indexes
        if not idx.name.startswith("sqlite_autoindex_")
    ]


def _diff_indexes(
    src: TableSnapshot, tgt: TableSnapshot, dialect: str, include_drops: bool
) -> list[DiffEntry]:
    entries: list[DiffEntry] = []
    src_idx = {i.name: i for i in src.indexes}
    tgt_idx = {i.name: i for i in tgt.indexes}

    if include_drops:
        for name, idx in tgt_idx.items():
            if name not in src_idx:
                entries.append(
                    DiffEntry(
                        kind="drop_index",
                        table=tgt.name,
                        detail=f"drop index {name}",
                        sql=[drop_index_sql(tgt.name, name, dialect)],
                    )
                )
    for name, idx in src_idx.items():
        if name in tgt_idx:
            if _index_identity(idx) == _index_identity(tgt_idx[name]):
                continue
            if include_drops:
                entries.append(
                    DiffEntry(
                        kind="drop_index",
                        table=tgt.name,
                        detail=f"drop index {name} (definition changed)",
                        sql=[drop_index_sql(tgt.name, name, dialect)],
                    )
                )
        entries.append(
            DiffEntry(
                kind="create_index",
                table=tgt.name,
                detail=f"create {'unique ' if idx.unique else ''}index {name} on ({', '.join(idx.columns)})",
                sql=[create_index_sql(tgt.name, name, idx.columns, idx.unique, dialect)],
            )
        )
    return entries


def migration_script(entries: list[DiffEntry], dialect: str) -> str:
    """Render entries as one commented SQL script."""
    lines = [f"-- DSMS migration ({dialect})", "-- Generated from a schema diff; review before applying."]
    if not entries:
        lines.append("-- Schemas are identical: nothing to do.")
        return "\n".join(lines)
    for entry in entries:
        lines.append("")
        lines.append(f"-- {entry.detail}" if entry.detail else f"-- {entry.kind} {entry.table}")
        lines.extend(entry.sql)
    return "\n".join(lines) + "\n"
