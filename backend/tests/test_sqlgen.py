"""Unit tests for the SQL generation module (no DB required)."""

import pytest

from app.sqlgen import (
    ColumnSpec,
    TableSpec,
    add_column_sql,
    create_table_sql,
    delete_row_sql,
    drop_table_sql,
    insert_row_sql,
    quote_ident,
    update_row_sql,
)


def _users() -> TableSpec:
    return TableSpec(
        name="users",
        columns=[
            ColumnSpec("id", "INTEGER", primary_key=True, nullable=False),
            ColumnSpec("name", "VARCHAR", nullable=False),
            ColumnSpec("age", "INTEGER", nullable=True, default="0"),
            ColumnSpec("email", "TEXT", unique=True),
        ],
    )


def test_create_table_sql_sqlite():
    sql = create_table_sql(_users(), "sqlite")
    assert 'CREATE TABLE "users"' in sql
    assert '"id" INTEGER PRIMARY KEY' in sql
    assert '"name" VARCHAR NOT NULL' in sql
    assert '"age" INTEGER DEFAULT 0' in sql
    assert '"email" TEXT UNIQUE' in sql


def test_create_table_sql_mysql_uses_backticks():
    sql = create_table_sql(_users(), "mysql")
    assert "CREATE TABLE `users`" in sql
    assert "`id` INTEGER PRIMARY KEY" in sql


def test_create_table_sql_requires_columns():
    with pytest.raises(ValueError):
        create_table_sql(TableSpec("empty", []), "sqlite")


def test_invalid_identifier_rejected():
    with pytest.raises(ValueError):
        create_table_sql(
            TableSpec("users; DROP TABLE x", [ColumnSpec("id", "INTEGER")]), "sqlite"
        )
    with pytest.raises(ValueError):
        quote_ident("bad-col;DROP TABLE t", "sqlite")


def test_invalid_type_rejected():
    with pytest.raises(ValueError):
        create_table_sql(
            TableSpec("t", [ColumnSpec("c", "TEXT); DROP TABLE x--")]), "sqlite"
        )


def test_add_column_sql():
    sql = add_column_sql("users", ColumnSpec("age", "INTEGER", default="0"), "sqlite")
    assert sql == 'ALTER TABLE "users" ADD COLUMN "age" INTEGER DEFAULT 0;'


def test_drop_column_sql():
    assert drop_table_sql("users", "sqlite") == 'DROP TABLE "users";'


def test_insert_row_sql_parameterized():
    sql, params = insert_row_sql("users", {"name": "Ada", "age": 37}, "sqlite")
    assert sql.startswith('INSERT INTO "users"')
    assert ":" in sql and params == {"__c0": "Ada", "__c1": 37}
    assert "Ada" not in sql  # value must be bound, never inlined


def test_update_row_sql_parameterized():
    sql, params = update_row_sql("users", {"name": "Ava"}, {"id": 1}, "sqlite")
    assert '"name" = :' in sql
    assert params == {"__v0": "Ava", "__w1": 1}


def test_delete_row_sql_parameterized():
    sql, params = delete_row_sql("users", {"id": 5}, "sqlite")
    assert '"id" = :' in sql
    assert params == {"__w0": 5}


def test_dml_requires_data():
    with pytest.raises(ValueError):
        insert_row_sql("t", {}, "sqlite")
    with pytest.raises(ValueError):
        update_row_sql("t", {}, {"id": 1}, "sqlite")
    with pytest.raises(ValueError):
        delete_row_sql("t", {}, "sqlite")