"""Unit tests for the SQL generation module (no DB required)."""

import pytest

from app.sqlgen import (
    ColumnSpec,
    ForeignKeySpec,
    IndexSpec,
    TableSpec,
    add_column_sql,
    count_rows_sql,
    create_foreign_key_sql,
    create_table_sql,
    delete_row_sql,
    drop_foreign_key_sql,
    drop_table_sql,
    insert_row_sql,
    quote_ident,
    rebuild_table_sql,
    select_rows_sql,
    update_row_sql,
    upsert_row_sql,
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


# --------------------------------------------------------------------- select


def test_select_all_no_filters():
    sql, params = select_rows_sql("users", None)
    assert sql == 'SELECT * FROM "users";'
    assert params == {}


def test_select_projection_and_eq():
    sql, params = select_rows_sql("users", ["id", "name"], eq={"age": 37})
    assert sql == 'SELECT "id", "name" FROM "users" WHERE "age" = :__f0;'
    assert params == {"__f0": 37}


def test_select_eq_null_uses_is_null():
    sql, _ = select_rows_sql("users", eq={"deleted_at": None})
    assert "deleted_at\" IS NULL" in sql
    assert ":__f0" not in sql


def test_select_where_operators():
    sql, params = select_rows_sql(
        "users",
        where=[
            ("age", "gte", 18),
            ("email", "like", "@gmail"),
            ("role", "in", ["admin", "moderator"]),
            ("banned_at", "is_null", None),
        ],
    )
    assert '"age" >= :__f0' in sql
    assert '"email" LIKE :__f1 ESCAPE \'\\\'' in sql
    assert '"role" IN (:__f2, :__f3)' in sql
    assert '"banned_at" IS NULL' in sql
    assert params == {"__f0": 18, "__f1": "%@gmail%", "__f2": "admin", "__f3": "moderator"}


def test_select_bad_operator_rejected():
    with pytest.raises(ValueError):
        select_rows_sql("users", where=[("age", "xor", 1)])


def test_select_search_or_like():
    sql, params = select_rows_sql(
        "users", search="50%_off", search_columns=["name", "email"]
    )
    assert "(\"name\" LIKE :__f0 ESCAPE '\\' OR \"email\" LIKE :__f1 ESCAPE '\\')" in sql
    # % and _ in the term must be escaped so they match literally.
    assert params["__f0"] == "%50\\%\\_off%"
    assert params["__f0"].count("\\%") == 1


def test_select_search_requires_columns():
    with pytest.raises(ValueError):
        select_rows_sql("users", search="ada")


def test_select_order_and_pagination():
    sql, params = select_rows_sql(
        "users",
        order_by=["name", "age"],
        order_dir="desc",
        limit=10,
        offset=20,
    )
    assert sql.endswith('ORDER BY "name" DESC, "age" DESC LIMIT :__f0 OFFSET :__f1;')
    assert params == {"__f0": 10, "__f1": 20}


def test_select_page_page_size():
    sql, params = select_rows_sql("users", page=3, page_size=25)
    assert sql.endswith('LIMIT :__f0 OFFSET :__f1;')
    assert params == {"__f0": 25, "__f1": 50}


def test_select_distinct():
    sql, _ = select_rows_sql("users", ["age"], distinct=True)
    assert sql.startswith('SELECT DISTINCT "age"')


def test_select_offset_requires_limit():
    with pytest.raises(ValueError):
        select_rows_sql("users", offset=10)


def test_select_ident_validation():
    with pytest.raises(ValueError):
        select_rows_sql("users", ["name; DROP TABLE t"])


def test_values_never_inlined():
    sql, params = select_rows_sql(
        "users", eq={"name": "Ada' OR '1'='1"}
    )
    assert "Ada" not in sql.replace(":__f0", "")
    assert params == {"__f0": "Ada' OR '1'='1"}


# --------------------------------------------------------------------- count


def test_count_simple():
    sql, params = count_rows_sql("users", eq={"age": 37})
    assert sql == 'SELECT COUNT(*) AS count FROM "users" WHERE "age" = :__f0;'
    assert params == {"__f0": 37}


def test_count_distinct():
    sql, _ = count_rows_sql("users", distinct_columns=["age"])
    assert sql == 'SELECT COUNT(DISTINCT "age") AS count FROM "users";'


# --------------------------------------------------------------------- upsert


def test_upsert_sqlite():
    sql, params = upsert_row_sql("users", {"id": 1, "name": "Ada"}, ["id"], "sqlite")
    assert sql == (
        'INSERT INTO "users" ("id", "name") VALUES (:__c0, :__c1) '
        'ON CONFLICT ("id") DO UPDATE SET "name" = excluded."name";'
    )
    assert params == {"__c0": 1, "__c1": "Ada"}


def test_upsert_mysql():
    sql, params = upsert_row_sql("users", {"id": 1, "name": "Ada"}, ["id"], "mysql")
    assert sql == (
        'INSERT INTO `users` (`id`, `name`) VALUES (:__c0, :__c1) '
        'ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);'
    )
    assert params == {"__c0": 1, "__c1": "Ada"}


def test_upsert_requires_conflict_and_update_cols():
    with pytest.raises(ValueError):
        upsert_row_sql("users", {"name": "Ada"}, [], "sqlite")
    with pytest.raises(ValueError):
        upsert_row_sql("users", {"id": 1}, ["id"], "sqlite")


# ------------------------------------------------------------------ foreign keys
def test_create_foreign_key_sql_postgresql():
    sql = create_foreign_key_sql(
        "posts", "fk_posts_user", ["user_id"], "users", ["id"], "CASCADE", "", "postgresql"
    )
    assert sql == (
        'ALTER TABLE "posts" ADD CONSTRAINT "fk_posts_user" FOREIGN KEY ("user_id") '
        'REFERENCES "users" ("id") ON DELETE CASCADE;'
    )


def test_create_foreign_key_sql_no_action_omitted():
    sql = create_foreign_key_sql(
        "posts", "fk_posts_user", ["user_id"], "users", ["id"], "NO ACTION", "NO ACTION", "mysql"
    )
    assert "ON DELETE" not in sql
    assert "ON UPDATE" not in sql
    assert sql.startswith("ALTER TABLE `posts` ADD CONSTRAINT `fk_posts_user` FOREIGN KEY")


def test_drop_foreign_key_sql():
    assert drop_foreign_key_sql("posts", "fk_posts_user", "mysql") == (
        "ALTER TABLE `posts` DROP FOREIGN KEY `fk_posts_user`;"
    )
    assert drop_foreign_key_sql("posts", "fk_posts_user", "postgresql") == (
        'ALTER TABLE "posts" DROP CONSTRAINT "fk_posts_user";'
    )


def test_create_foreign_key_length_mismatch():
    with pytest.raises(ValueError):
        create_foreign_key_sql("a", "f", ["x"], "b", ["y", "z"], dialect="postgresql")


def test_rebuild_table_sql_sqlite():
    statements = rebuild_table_sql(
        "posts",
        [ColumnSpec("id", "INTEGER", primary_key=True, nullable=False), ColumnSpec("user_id", "INTEGER")],
        [ForeignKeySpec("fk_posts_user", ["user_id"], "users", ["id"], "CASCADE", "")],
        [IndexSpec("idx_posts_user", ["user_id"])],
        "sqlite",
    )
    assert statements[0].startswith('CREATE TABLE "posts_rebuild" (')
    assert "CONSTRAINT \"fk_posts_user\" FOREIGN KEY (\"user_id\") REFERENCES \"users\" (\"id\") ON DELETE CASCADE" in statements[0]
    assert statements[1] == (
        'INSERT INTO "posts_rebuild" ("id", "user_id") '
        'SELECT "id", "user_id" FROM "posts";'
    )
    assert statements[2] == 'DROP TABLE "posts";'
    assert statements[3] == 'ALTER TABLE "posts_rebuild" RENAME TO "posts";'
    assert statements[4].startswith("CREATE INDEX \"idx_posts_user\"")


def test_rebuild_table_sql_composite_pk():
    statements = rebuild_table_sql(
        "post_tags",
        [
            ColumnSpec("post_id", "INTEGER", primary_key=True, nullable=False),
            ColumnSpec("tag_id", "INTEGER", primary_key=True, nullable=False),
        ],
        [],
        [],
        "sqlite",
    )
    assert 'PRIMARY KEY ("post_id", "tag_id")' in statements[0]
    assert statements[0].count("PRIMARY KEY") == 1


def test_create_table_sql_composite_pk():
    table = TableSpec(
        name="post_tags",
        columns=[
            ColumnSpec("post_id", "INTEGER", primary_key=True, nullable=False),
            ColumnSpec("tag_id", "INTEGER", primary_key=True, nullable=False),
        ],
    )
    sql = create_table_sql(table, "sqlite")
    assert 'PRIMARY KEY ("post_id", "tag_id")' in sql
    assert sql.count("PRIMARY KEY") == 1