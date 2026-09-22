"""Pure SQL generation. No engine/connection imports — this module only
turns structured table/column/row descriptions into SQL strings.

DML helpers return ``(statement, params)`` pairs where values are always
bound parameters so generated SQL can be executed safely via
``sqlalchemy.text``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
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


@dataclass
class IndexSpec:
    name: str
    columns: list[str]
    unique: bool = False


@dataclass
class ForeignKeySpec:
    name: str
    columns: list[str]
    referred_table: str
    referred_columns: list[str]
    on_delete: str = ""
    on_update: str = ""


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


def _column_sql(col: ColumnSpec, dialect: str, composite_pk: bool = False) -> str:
    validate_ident(col.name)
    validate_type(col.data_type)
    parts = [quote_ident(col.name, dialect), col.data_type.upper()]
    if col.primary_key and not composite_pk:
        parts.append("PRIMARY KEY")
    elif not col.nullable:
        parts.append("NOT NULL")
    if col.unique:
        parts.append("UNIQUE")
    if col.default is not None:
        parts.append(f"DEFAULT {col.default}")
    return " ".join(p for p in parts if p)


def create_table_sql(
    table: TableSpec,
    dialect: str = "sqlite",
    foreign_keys: list[ForeignKeySpec] | None = None,
) -> str:
    """Render ``CREATE TABLE`` for ``table``.

    ``foreign_keys`` (optional) are rendered as inline ``CONSTRAINT ... FOREIGN
    KEY`` clauses — valid on all three supported dialects.
    """
    if not table.columns:
        raise ValueError("A table must have at least one column.")
    primary_keys = [c.name for c in table.columns if c.primary_key]
    composite = len(primary_keys) > 1
    lines = [_column_sql(c, dialect, composite) for c in table.columns]
    if composite:
        pk = ", ".join(quote_ident(c, dialect) for c in primary_keys)
        lines.append(f"PRIMARY KEY ({pk})")
    for fk in foreign_keys or []:
        lines.append(_fk_clause(fk, dialect))
    body = ",\n    ".join(lines)
    return f"CREATE TABLE {quote_ident(table.name, dialect)} (\n    {body}\n);"


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


def rename_column_sql(
    table_name: str, old_name: str, new_name: str, dialect: str = "sqlite"
) -> str:
    """Build ``ALTER TABLE ... RENAME COLUMN``.

    Supported natively by SQLite (>= 3.25), PostgreSQL, and MySQL (>= 8.0).
    On SQLite this form also updates foreign-key definitions in other tables
    that reference the renamed column.
    """
    q = quote_ident
    return (
        f"ALTER TABLE {q(table_name, dialect)} "
        f"RENAME COLUMN {q(old_name, dialect)} TO {q(new_name, dialect)};"
    )


def modify_column_sql(
    table_name: str, col: ColumnSpec, dialect: str = "sqlite"
) -> list[str]:
    """Statements changing a column's type, nullability, or default.

    ``col`` must describe the *target* definition; primary_key/unique flags
    are ignored (constraint changes are not supported here).

    * postgresql: separate ``ALTER COLUMN`` statements per property.
    * mysql: one ``MODIFY COLUMN`` statement with the full definition.
    * sqlite: has no ``ALTER`` for these — callers must use
      :func:`rebuild_table_sql` instead, which raises here.
    """
    validate_ident(col.name)
    validate_type(col.data_type)
    q = quote_ident(table_name, dialect)
    c = quote_ident(col.name, dialect)
    if dialect == "sqlite":
        raise ValueError(
            "SQLite cannot ALTER a column definition in place; "
            "rebuild the table via rebuild_table_sql()."
        )
    if dialect == "mysql":
        parts = [c, col.data_type.upper()]
        if not col.nullable:
            parts.append("NOT NULL")
        if col.default is not None:
            parts.append(f"DEFAULT {col.default}")
        return [f"ALTER TABLE {q} MODIFY COLUMN {' '.join(parts)};"]
    # postgresql
    statements = [f"ALTER TABLE {q} ALTER COLUMN {c} TYPE {col.data_type.upper()};"]
    statements.append(
        f"ALTER TABLE {q} ALTER COLUMN {c} SET NOT NULL;"
        if not col.nullable
        else f"ALTER TABLE {q} ALTER COLUMN {c} DROP NOT NULL;"
    )
    if col.default is not None:
        statements.append(
            f"ALTER TABLE {q} ALTER COLUMN {c} SET DEFAULT {col.default};"
        )
    else:
        statements.append(f"ALTER TABLE {q} ALTER COLUMN {c} DROP DEFAULT;")
    return statements


def create_index_sql(
    table_name: str,
    index_name: str,
    columns: list[str],
    unique: bool = False,
    dialect: str = "sqlite",
) -> str:
    validate_ident(index_name)
    if not columns:
        raise ValueError("An index must cover at least one column.")
    cols = ", ".join(quote_ident(c, dialect) for c in columns)
    prefix = "CREATE UNIQUE INDEX" if unique else "CREATE INDEX"
    return (
        f"{prefix} {quote_ident(index_name, dialect)} "
        f"ON {quote_ident(table_name, dialect)} ({cols});"
    )


def drop_index_sql(table_name: str, index_name: str, dialect: str = "sqlite") -> str:
    validate_ident(index_name)
    quoted = quote_ident(index_name, dialect)
    if dialect == "mysql":
        return f"DROP INDEX {quoted} ON {quote_ident(table_name, dialect)};"
    return f"DROP INDEX {quoted};"


#: Referential actions emitted by :func:`create_foreign_key_sql`. `""` and
#: `"NO ACTION"` omit the clause (both mean "no action" in most engines).
FK_ACTIONS = {"", "NO ACTION", "RESTRICT", "CASCADE", "SET NULL", "SET DEFAULT"}


def create_foreign_key_sql(
    table_name: str,
    constraint_name: str,
    columns: list[str],
    referred_table: str,
    referred_columns: list[str],
    on_delete: str = "",
    on_update: str = "",
    dialect: str = "sqlite",
) -> str:
    """Build an ``ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY`` statement.

    Supported natively by PostgreSQL and MySQL. SQLite has no ``ALTER`` support
    for foreign keys — use :func:`rebuild_table_sql` for it instead.

    Args:
        table_name: Child table identifier.
        constraint_name: Constraint name (required on PG/MySQL).
        columns: Local column(s) holding the reference.
        referred_table: Parent table identifier.
        referred_columns: Referenced column(s) on the parent.
        on_delete: Referential action (CASCADE, SET NULL, …) or "" / NO ACTION.
        on_update: Referential action or "" / NO ACTION.
        dialect: ``"sqlite"``, ``"postgresql"``, or ``"mysql"``.

    Raises:
        ValueError: On invalid identifiers, length mismatch, or invalid actions.

    Example:
        ``create_foreign_key_sql("posts", "fk_posts_user", ["user_id"],
        "users", ["id"], "CASCADE", "", "postgresql")`` →
        ``ALTER TABLE "posts" ADD CONSTRAINT "fk_posts_user" FOREIGN KEY
        ("user_id") REFERENCES "users" ("id") ON DELETE CASCADE;``
    """
    if not columns or len(columns) != len(referred_columns):
        raise ValueError(
            "columns and referred_columns must be non-empty and match in length."
        )
    if on_delete not in FK_ACTIONS or on_update not in FK_ACTIONS:
        raise ValueError(
            f"Invalid referential action (got delete={on_delete!r}, update={on_update!r})."
        )
    local = ", ".join(quote_ident(c, dialect) for c in columns)
    refs = ", ".join(quote_ident(c, dialect) for c in referred_columns)
    statement = (
        f"ALTER TABLE {quote_ident(table_name, dialect)} "
        f"ADD CONSTRAINT {quote_ident(constraint_name, dialect)} "
        f"FOREIGN KEY ({local}) REFERENCES {quote_ident(referred_table, dialect)} ({refs})"
    )
    if on_delete and on_delete != "NO ACTION":
        statement += f" ON DELETE {on_delete}"
    if on_update and on_update != "NO ACTION":
        statement += f" ON UPDATE {on_update}"
    return statement + ";"


def drop_foreign_key_sql(
    table_name: str, constraint_name: str, dialect: str = "sqlite"
) -> str:
    """Build an ``ALTER TABLE ... DROP`` statement for a foreign key.

    MySQL drops via ``DROP FOREIGN KEY``, PostgreSQL via ``DROP CONSTRAINT``.
    SQLite has no equivalent — drop by rebuilding the table with
    :func:`rebuild_table_sql`.
    """
    validate_ident(constraint_name)
    quoted = quote_ident(constraint_name, dialect)
    if dialect == "mysql":
        return (
            f"ALTER TABLE {quote_ident(table_name, dialect)} DROP FOREIGN KEY {quoted};"
        )
    return f"ALTER TABLE {quote_ident(table_name, dialect)} DROP CONSTRAINT {quoted};"


def _fk_clause(fk: ForeignKeySpec, dialect: str) -> str:
    if not fk.columns or len(fk.columns) != len(fk.referred_columns):
        raise ValueError(
            "columns and referred_columns must be non-empty and match in length."
        )
    clause = (
        f"CONSTRAINT {quote_ident(fk.name, dialect)} "
        f"FOREIGN KEY ({', '.join(quote_ident(c, dialect) for c in fk.columns)}) "
        f"REFERENCES {quote_ident(fk.referred_table, dialect)} "
        f"({', '.join(quote_ident(c, dialect) for c in fk.referred_columns)})"
    )
    if fk.on_delete and fk.on_delete != "NO ACTION":
        clause += f" ON DELETE {fk.on_delete}"
    if fk.on_update and fk.on_update != "NO ACTION":
        clause += f" ON UPDATE {fk.on_update}"
    return clause


def rebuild_table_sql(
    table_name: str,
    columns: list[ColumnSpec],
    foreign_keys: list[ForeignKeySpec],
    indexes: list[IndexSpec],
    dialect: str = "sqlite",
    source_columns: list[str] | None = None,
) -> list[str]:
    """Return the statements that recreate ``table`` with updated constraints
    (SQLite has no ``ALTER`` for foreign keys or column definitions).

    The table is copied to a temporary name, column data is copied verbatim,
    the old table is dropped, the temporary one is renamed back, and indexes
    are recreated. All statements must run in a single transaction for safety.

    Args:
        table_name: Table identifier.
        columns: Full column definitions of the recreated table.
        foreign_keys: Foreign keys after the change (included inline).
        indexes: Indexes to recreate after the rename (skip the ones SQLite
            owns, e.g. ``sqlite_autoindex_*``).
        dialect: Target dialect.
        source_columns: Names of the columns in the *current* table, aligned
            1:1 with ``columns``. The ``INSERT ... SELECT`` copies
            ``source_columns[i]`` into ``columns[i]`` — pass a mapping when a
            column is renamed, and omit a column (with its position pruned
            from both lists consistently) only when its data is dropped.
            Defaults to the names in ``columns`` (identity mapping).

    Returns:
        Ordered list of SQL statements.
    """
    if source_columns is not None and len(source_columns) != len(columns):
        raise ValueError("source_columns must align 1:1 with columns.")
    tmp_name = f"{table_name}_rebuild"
    pks = [c.name for c in columns if c.primary_key]
    composite = len(pks) > 1
    lines = [_column_sql(c, dialect, composite) for c in columns]
    if composite:
        pk = ", ".join(quote_ident(c, dialect) for c in pks)
        lines.append(f"PRIMARY KEY ({pk})")
    for fk in foreign_keys:
        lines.append(_fk_clause(fk, dialect))
    body = ",\n    ".join(lines)
    column_names = [c.name for c in columns]
    source = source_columns if source_columns is not None else column_names

    statements = [
        (f"CREATE TABLE {quote_ident(tmp_name, dialect)} (\n    {body}\n);"),
    ]
    target_quoted = ", ".join(quote_ident(c, dialect) for c in column_names)
    source_quoted = ", ".join(quote_ident(c, dialect) for c in source)
    statements.append(
        f"INSERT INTO {quote_ident(tmp_name, dialect)} ({target_quoted}) "
        f"SELECT {source_quoted} FROM {quote_ident(table_name, dialect)};"
    )
    statements.append(f"DROP TABLE {quote_ident(table_name, dialect)};")
    statements.append(
        f"ALTER TABLE {quote_ident(tmp_name, dialect)} RENAME TO {quote_ident(table_name, dialect)};"
    )
    for index in indexes:
        statements.append(
            create_index_sql(
                table_name, index.name, index.columns, index.unique, dialect
            )
        )
    return statements


def insert_row_sql(
    table_name: str, data: dict[str, object], dialect: str = "sqlite"
) -> tuple[str, dict[str, object]]:
    """Build a parameterized ``INSERT`` statement for a single row.

    Args:
        table_name: Target table identifier.
        data: Column values, ``{column: value}``. Keys are validated and
            quoted for the dialect; values are always bound parameters.
        dialect: ``"sqlite"``, ``"postgresql"``, or ``"mysql"``.

    Returns:
        ``(sql, params)`` where ``sql`` uses ``:name`` placeholders and
        ``params`` maps each placeholder to its value.

    Raises:
        ValueError: If ``data`` is empty or a column name is invalid.

    Example:
        ``insert_row_sql("users", {"name": "Ada", "age": 37})`` →
        ``('INSERT INTO "users" ("name", "age") VALUES (:__c0, :__c1);',
          {'__c0': 'Ada', '__c1': 37})``

    Dialect notes:
        Identifiers are quoted with backticks on MySQL and double quotes on
        PostgreSQL/SQLite. Inserting the integer primary key works on all
        three engines; auto-increment is only automatic on SQLite.
    """
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
    """Build a parameterized ``UPDATE`` for one or more rows matched by ``pk``.

    Args:
        table_name: Target table identifier.
        data: Columns to change, ``{column: value}``. Values are bound.
        pk: Equality filter identifying the target row(s), ``{column: value}``.
            Every key is ANDed into the ``WHERE`` clause.
        dialect: ``"sqlite"``, ``"postgresql"``, or ``"mysql"``.

    Returns:
        ``(sql, params)`` with ``:name`` placeholders for both set values
        (``__vN``) and primary-key filters (``__wN``).

    Raises:
        ValueError: If ``data`` or ``pk`` is empty.

    Example:
        ``update_row_sql("users", {"name": "Ava"}, {"id": 1})`` →
        ``('UPDATE "users" SET "name" = :__v0 WHERE "id" = :__w1;',
          {'__v0': 'Ava', '__w1': 1})``
    """
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
    """Build a parameterized ``DELETE`` matched by primary-key equality.

    Args:
        table_name: Target table identifier.
        pk: Equality filter, ``{column: value}``; ANDed into ``WHERE``.
        dialect: ``"sqlite"``, ``"postgresql"``, or ``"mysql"``.

    Returns:
        ``(sql, params)``; PK filter values are bound as ``__wN``.

    Raises:
        ValueError: If ``pk`` is empty.

    Example:
        ``delete_row_sql("users", {"id": 5})`` →
        ``('DELETE FROM "users" WHERE "id" = :__w0;', {'__w0': 5})``
    """
    if not pk:
        raise ValueError("Delete requires a primary key.")
    params: dict[str, object] = {}
    wheres = []
    for k, v in pk.items():
        param = f"__w{len(params)}"
        wheres.append(f"{quote_ident(k, dialect)} = :{param}")
        params[param] = v
    sql = (
        f"DELETE FROM {quote_ident(table_name, dialect)} WHERE {' AND '.join(wheres)};"
    )
    return sql, params


#: Operator names accepted by `where`/`eq` filters, mapped to SQL operators.
_OPS = {
    "eq": "=",
    "=": "=",
    "ne": "<>",
    "!=": "<>",
    "<>": "<>",
    "lt": "<",
    "<": "<",
    "lte": "<=",
    "<=": "<=",
    "gt": ">",
    ">": ">",
    "gte": ">=",
    ">=": ">=",
    "like": "LIKE",
    "not_like": "NOT LIKE",
    "ilike": "ILIKE",
    "in": "IN",
    "not_in": "NOT IN",
    "is_null": "IS NULL",
    "is_not_null": "IS NOT NULL",
    "IS NULL": "IS NULL",
    "IS NOT NULL": "IS NOT NULL",
}


def _like_pattern(value: object) -> str:
    """Escape a search term into a ``%…%`` LIKE pattern.

    Backslashes, ``%`` and ``_`` are escaped so user input is treated
    literally; the term is wrapped in ``%`` for substring matching.
    """
    raw = str(value).replace("\\", "\\\\")
    raw = raw.replace("%", "\\%").replace("_", "\\_")
    return f"%{raw}%"


def _condition_sql(
    col: str, op: str, value: object, params: dict[str, object], dialect: str
) -> str:
    """Render one ``col op value`` predicate, binding the value if needed."""
    q = quote_ident(col, dialect)
    if op == "IS NULL":
        return f"{q} IS NULL"
    if op == "IS NOT NULL":
        return f"{q} IS NOT NULL"
    # LIKE/ILIKE escape the value; stored as a plain text pattern.
    if op in ("LIKE", "ILIKE", "NOT LIKE"):
        param = f"__f{len(params)}"
        params[param] = _like_pattern(value)
        return f"{q} {op} :{param} ESCAPE '\\'"
    if op in ("IN", "NOT IN"):
        values = list(value) if isinstance(value, (list, tuple)) else [value]
        if not values:
            raise ValueError(f"{op} requires at least one value.")
        params_list = [f"__f{len(params) + i}" for i in range(len(values))]
        for i, v in enumerate(values):
            params[params_list[i]] = v
        return f"{q} {op} ({', '.join(':' + p for p in params_list)})"
    param = f"__f{len(params)}"
    params[param] = value
    return f"{q} {op} :{param}"


def _filters_sql(
    eq: dict[str, object] | None,
    where: Iterable[tuple[str, str, object]] | None,
    search: str | None,
    search_columns: Iterable[str] | None,
    dialect: str,
) -> tuple[str, dict[str, object]]:
    """Combine ``eq``/``where``/``search`` into a ``WHERE`` clause.

    Returns ``(clause, params)``; ``clause`` is ``"WHERE ..."`` when any
    predicate exists, otherwise an empty string with empty params.
    """
    params: dict[str, object] = {}
    parts: list[str] = []
    for col, value in (eq or {}).items():
        parts.append(
            _condition_sql(
                col, "=" if value is not None else "IS NULL", value, params, dialect
            )
        )
    for col, op, value in where or []:
        sql_op = _OPS.get(op)
        if sql_op is None:
            raise ValueError(f"Unsupported operator {op!r}.")
        parts.append(_condition_sql(col, sql_op, value, params, dialect))
    if search is not None:
        cols = list(search_columns) if search_columns is not None else []
        if not cols:
            raise ValueError(
                "search requires `search_columns` (the columns to search)."
            )
        searched: list[str] = []
        for col in cols:
            param = f"__f{len(params)}"
            params[param] = _like_pattern(search)
            searched.append(f"{quote_ident(col, dialect)} LIKE :{param} ESCAPE '\\'")
        parts.append("(" + " OR ".join(searched) + ")")
    if not parts:
        return "", {}
    return "WHERE " + " AND ".join(parts), params


def _pagination_sql(
    limit: int | None,
    offset: int | None,
    page: int | None,
    page_size: int | None,
) -> tuple[int | None, int | None]:
    """Resolve ``limit``/``offset`` from direct values or ``page``/``page_size``.

    ``page`` is 1-based: ``offset = (page - 1) * page_size``. Direct values
    take precedence over the pagination pair.
    """
    if page is not None or page_size is not None:
        size = page_size if page_size is not None else 20
        num = page if page is not None else 1
        if size < 1:
            raise ValueError("page_size must be >= 1.")
        if num < 1:
            raise ValueError("page must be >= 1 (1-based).")
        return size, (num - 1) * size
    if limit is not None and limit < 1:
        raise ValueError("limit must be >= 1.")
    if offset is not None and offset < 0:
        raise ValueError("offset must be >= 0.")
    if offset is not None and limit is None:
        raise ValueError(
            "OFFSET requires LIMIT (or use page/page_size) for portability."
        )
    return limit, offset


def select_rows_sql(
    table_name: str,
    columns: Iterable[str] | None = None,
    *,
    eq: dict[str, object] | None = None,
    where: Iterable[tuple[str, str, object]] | None = None,
    search: str | None = None,
    search_columns: Iterable[str] | None = None,
    distinct: bool = False,
    order_by: str | Iterable[str] | None = None,
    order_dir: str = "asc",
    limit: int | None = None,
    offset: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
    dialect: str = "sqlite",
) -> tuple[str, dict[str, object]]:
    """Build a parameterized ``SELECT`` (the ``get`` verb).

    Every predicate value is a bound parameter — nothing is inlined.

    Args:
        table_name: Target table identifier.
        columns: Projection list; ``None``/empty selects ``*``. Each name is
            validated and quoted for the dialect.
        eq: Equality filters, ``{column: value}`` (ANDed). ``None`` yields
            ``IS NULL``.
        where: Comparison filters as ``(column, operator, value)`` tuples,
            ANDed together and with ``eq``. Supported operators (with aliases):
            ``=``/``eq``, ``!=``/``ne``, ``<``/``lt``, ``<=``/``lte``,
            ``>``/``gt``, ``>=``/``gte``, ``LIKE``, ``ILIKE`` (PostgreSQL),
            ``IN``, ``NOT IN``, ``IS NULL``, ``IS NOT NULL``.
            For ``IN``/``NOT IN`` pass a list as the value.
        search: Substring term matched with ``LIKE`` against every column in
            ``search_columns`` (ORed; wildcards in the term are escaped).
        search_columns: Columns to run ``search`` against. Required when
            ``search`` is set.
        distinct: Emit ``SELECT DISTINCT``.
        order_by: Column name or list of column names to sort by.
        order_dir: ``"asc"`` or ``"desc"``; applied to every ``order_by`` column.
        limit: Maximum rows (>= 1).
        offset: Row offset (>= 0); requires ``limit`` (portable across
            SQLite/PostgreSQL/MySQL).
        page: 1-based page number; combined with ``page_size`` produces the
            same effect as ``limit``/``offset`` and takes precedence over them.
        page_size: Rows per page (>= 1, default 20 when ``page`` is used).
        dialect: ``"sqlite"``, ``"postgresql"``, or ``"mysql"``.

    Returns:
        ``(sql, params)``; filter values are bound as ``__fN``.

    Raises:
        ValueError: On invalid identifiers, unsupported operators, or invalid
            pagination arguments.

    Example:
        ``select_rows_sql("users", ["id", "name"], eq={"age": 37},
          where=[("email", "like", "@gmail")], search="ad",
          search_columns=["name"], order_by="name", page=2, page_size=10)``
        → ``SELECT "id", "name" FROM "users" WHERE "age" = :__f0 AND
          "email" LIKE :__f1 ESCAPE '\\' AND ("name" LIKE :__f2 ESCAPE '\\')
          ORDER BY "name" ASC LIMIT :__f3 OFFSET :__f4``
          (with the four values bound in ``params``).
    """
    proj = ", ".join(quote_ident(c, dialect) for c in columns) if columns else "*"
    statement = "SELECT DISTINCT" if distinct else "SELECT"
    clause, params = _filters_sql(eq, where, search, search_columns, dialect)
    sql = f"{statement} {proj} FROM {quote_ident(table_name, dialect)}"
    if clause:
        sql += " " + clause
    if order_by:
        cols = [order_by] if isinstance(order_by, str) else list(order_by)
        dir_sql = "DESC" if order_dir.lower() == "desc" else "ASC"
        sql += " ORDER BY " + ", ".join(
            f"{quote_ident(c, dialect)} {dir_sql}" for c in cols
        )
    resolved_limit, resolved_offset = _pagination_sql(limit, offset, page, page_size)
    if resolved_limit is not None:
        param = f"__f{len(params)}"
        params[param] = resolved_limit
        sql += f" LIMIT :{param}"
    if resolved_offset is not None:
        param = f"__f{len(params)}"
        params[param] = resolved_offset
        sql += f" OFFSET :{param}"
    return sql + ";", params


def count_rows_sql(
    table_name: str,
    *,
    eq: dict[str, object] | None = None,
    where: Iterable[tuple[str, str, object]] | None = None,
    search: str | None = None,
    search_columns: Iterable[str] | None = None,
    distinct_columns: Iterable[str] | None = None,
    dialect: str = "sqlite",
) -> tuple[str, dict[str, object]]:
    """Build a parameterized ``SELECT COUNT(*)`` matching the same filters as
    :func:`select_rows_sql` (useful for pagination metadata).

    Args:
        table_name: Target table identifier.
        eq/where/search/search_columns: Identical semantics to
            :func:`select_rows_sql`.
        distinct_columns: When set, counts distinct combinations of these
            columns instead of all rows (``COUNT(DISTINCT ...)``).
        dialect: ``"sqlite"``, ``"postgresql"``, or ``"mysql"``.

    Returns:
        ``(sql, params)``.

    Example:
        ``count_rows_sql("users", eq={"age": 37})`` →
        ``('SELECT COUNT(*) AS count FROM "users" WHERE "age" = :__f0;',
          {'__f0': 37})``
    """
    expr = "COUNT(*) AS count"
    if distinct_columns:
        cols = ", ".join(quote_ident(c, dialect) for c in distinct_columns)
        expr = f"COUNT(DISTINCT {cols}) AS count"
    clause, params = _filters_sql(eq, where, search, search_columns, dialect)
    sql = f"SELECT {expr} FROM {quote_ident(table_name, dialect)}"
    if clause:
        sql += " " + clause
    return sql + ";", params


def upsert_row_sql(
    table_name: str,
    data: dict[str, object],
    conflict_columns: list[str],
    dialect: str = "sqlite",
) -> tuple[str, dict[str, object]]:
    """Build a parameterized upsert (the ``put`` verb): ``INSERT`` that updates
    the row on a conflict with the given columns, or creates it otherwise.

    Args:
        table_name: Target table identifier.
        data: Column values, ``{column: value}``; bound as parameters.
        conflict_columns: The unique/PK columns that detect an existing row.
            Values given for them are included in the insert.
        dialect: ``"sqlite"``, ``"postgresql"``, or ``"mysql"``.

    Returns:
        ``(sql, params)``.

    Raises:
        ValueError: If ``data`` is empty or conflict columns are not provided.

    Dialect notes:
        * sqlite/postgresql: ``INSERT ... ON CONFLICT (cols) DO UPDATE SET ...
          excluded.<col>``.
        * mysql: ``INSERT ... ON DUPLICATE KEY UPDATE <col> = VALUES(<col>)``.

    Example:
        ``upsert_row_sql("users", {"id": 1, "name": "Ada"}, ["id"])`` →
        ``('INSERT INTO "users" ("id", "name") VALUES (:__c0, :__c1)
          ON CONFLICT ("id") DO UPDATE SET "name" = excluded."name";',
          {'__c0': 1, '__c1': 'Ada'})``
    """
    if not data:
        raise ValueError("Upsert requires at least one column value.")
    if not conflict_columns:
        raise ValueError("Upsert requires the conflict (PK/unique) columns.")
    insert_frag, params = insert_row_sql(table_name, data, dialect)
    insert_frag = insert_frag.rstrip(";")
    conflict = ", ".join(quote_ident(c, dialect) for c in conflict_columns)
    conflict_set = {c for c in conflict_columns}
    update_cols = [c for c in data if c not in conflict_set]
    if dialect == "mysql":
        if not update_cols:
            raise ValueError(
                "UPSERT needs at least one updateable (non-conflict) column."
            )
        update = ", ".join(
            f"{quote_ident(c, dialect)} = VALUES({quote_ident(c, dialect)})"
            for c in update_cols
        )
        return f"{insert_frag} ON DUPLICATE KEY UPDATE {update};", params
    if not update_cols:
        raise ValueError("UPSERT needs at least one updateable (non-conflict) column.")
    update = ", ".join(
        f"{quote_ident(c, dialect)} = excluded.{quote_ident(c, dialect)}"
        for c in update_cols
    )
    return f"{insert_frag} ON CONFLICT ({conflict}) DO UPDATE SET {update};", params


# =============================================================================
# SQL generation method reference
# -----------------------------------------------------------------------------
# DDL (return a plain SQL string):
#   create_table_sql(table, dialect)   — CREATE TABLE from a TableSpec
#   drop_table_sql(table, dialect)     — DROP TABLE
#   add_column_sql(table, col, dialect)  — ALTER TABLE ... ADD COLUMN
#   drop_column_sql(table, col, dialect) — ALTER TABLE ... DROP COLUMN
#   rename_column_sql(table, old, new, dialect) — ALTER TABLE ... RENAME COLUMN
#   modify_column_sql(table, col, dialect) — type/nullability/default change
#                          (postgresql: ALTER COLUMN ...; mysql: MODIFY COLUMN;
#                           sqlite: use rebuild_table_sql instead)
#   create_index_sql(table, index, cols, unique, dialect) — CREATE [UNIQUE] INDEX
#   drop_index_sql(table, index, dialect) — DROP INDEX (mysql: ... ON table)
#   create_foreign_key_sql(table, name, cols, ref_table, ref_cols,
#                          on_delete, on_update, dialect) — ALTER ... ADD CONSTRAINT
#   drop_foreign_key_sql(table, name, dialect) — DROP CONSTRAINT / DROP FOREIGN KEY
#   rebuild_table_sql(table, columns, foreign_keys, indexes, dialect)
#                          — SQLite FK changes via table-copy rebuild
# DML/query (return (sql, params); values are always bound, never inlined):
#   create / insert  -> insert_row_sql(table, data, dialect)
#   get              -> select_rows_sql(table, columns=..., eq=..., where=...,
#                        search=..., search_columns=..., distinct=..., order_by=...,
#                        order_dir=..., limit=..., offset=..., page=...,
#                        page_size=..., dialect=...)
#   search           -> fold `search` + `search_columns` into select_rows_sql
#   count            -> count_rows_sql(table, eq=..., where=..., search=...,
#                        search_columns=..., distinct_columns=..., dialect=...)
#   update           -> update_row_sql(table, data, pk, dialect)
#   put (upsert)     -> upsert_row_sql(table, data, conflict_columns, dialect)
#   delete           -> delete_row_sql(table, pk, dialect)
# =============================================================================
