"""API integration tests running against an in-memory SQLite connection."""

import json
import os
import tempfile


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_connection(client):
    res = client.post("/api/connections", json={"name": "mem", "dialect": "sqlite"})
    assert res.status_code == 201
    body = res.json()
    assert body["id"]
    assert body["dialect"] == "sqlite"
    assert "sqlite" in body["url"]
    assert "password" not in body["url"]


def test_create_connection_failure(client):
    with tempfile.TemporaryDirectory() as tmp:
        res = client.post(
            "/api/connections",
            json={"name": "bad", "dialect": "sqlite", "file": tmp},
        )
    assert res.status_code == 400


def test_list_and_delete_connections(client, mem_conn):
    names = [c["name"] for c in client.get("/api/connections").json()]
    assert "mem" in names

    res = client.delete(f"/api/connections/{mem_conn}")
    assert res.status_code == 204
    names = [c["name"] for c in client.get("/api/connections").json()]
    assert "mem" not in names


def _create_table(client, conn_id, name="users"):
    res = client.post(
        f"/api/connections/{conn_id}/tables",
        json={
            "name": name,
            "columns": [
                {"name": "id", "data_type": "INTEGER", "primary_key": True, "nullable": False},
                {"name": "name", "data_type": "VARCHAR", "nullable": False},
                {"name": "age", "data_type": "INTEGER", "nullable": True, "default": "0"},
            ],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_create_and_list_tables(client, mem_conn):
    table = _create_table(client, mem_conn)
    assert table["name"] == "users"
    columns = {c["name"]: c for c in table["columns"]}
    assert columns["id"]["primary_key"] is True
    assert columns["id"]["nullable"] is False
    assert columns["age"]["nullable"] is True

    names = [t["name"] for t in client.get(f"/api/connections/{mem_conn}/tables").json()]
    assert "users" in names


def test_duplicate_table_conflict(client, mem_conn):
    _create_table(client, mem_conn)
    res = client.post(
        f"/api/connections/{mem_conn}/tables",
        json={"name": "users", "columns": [{"name": "id", "data_type": "INTEGER"}]},
    )
    assert res.status_code == 409


def test_create_adds_auto_columns(client, mem_conn):
    res = client.post(
        f"/api/connections/{mem_conn}/tables",
        json={"name": "notes", "columns": [{"name": "body", "data_type": "TEXT", "nullable": False}]},
    )
    assert res.status_code == 201, res.text
    cols = {c["name"]: c for c in res.json()["columns"]}
    assert cols["_id"]["primary_key"] is True
    assert cols["_id"]["nullable"] is False
    assert cols["created_at"]["nullable"] is False
    assert cols["created_at"]["default"] is not None
    assert cols["updated_at"]["nullable"] is False
    assert cols["updated_at"]["default"] is not None


def test_create_keeps_user_primary_key(client, mem_conn):
    _create_table(client, mem_conn)
    users = next(t for t in client.get(f"/api/connections/{mem_conn}/tables").json() if t["name"] == "users")
    names = [c["name"] for c in users["columns"]]
    assert "_id" not in names
    assert "created_at" in names and "updated_at" in names


def test_create_does_not_duplicate_auto_columns(client, mem_conn):
    res = client.post(
        f"/api/connections/{mem_conn}/tables",
        json={"name": "events", "columns": [{"name": "created_at", "data_type": "TEXT"}]},
    )
    assert res.status_code == 201, res.text
    names = [c["name"] for c in res.json()["columns"]]
    assert names.count("created_at") == 1
    assert "_id" in names and "updated_at" in names


def test_create_exclude_auto_columns(client, mem_conn):
    res = client.post(
        f"/api/connections/{mem_conn}/tables",
        json={
            "name": "audit",
            "columns": [{"name": "body", "data_type": "TEXT", "nullable": False}],
            "exclude_auto": ["created_at"],
        },
    )
    assert res.status_code == 201, res.text
    names = [c["name"] for c in res.json()["columns"]]
    assert "created_at" not in names
    assert "_id" in names and "updated_at" in names
    assert names.count("created_at") == 0


def test_table_sql_endpoint(client, mem_conn):
    _create_table(client, mem_conn)
    res = client.get(f"/api/connections/{mem_conn}/tables/users/sql")
    assert res.status_code == 200
    assert 'CREATE TABLE "users"' in res.json()["sql"]


def test_add_and_drop_column(client, mem_conn):
    _create_table(client, mem_conn)
    res = client.post(
        f"/api/connections/{mem_conn}/tables/users/columns",
        json={"name": "email", "data_type": "TEXT", "nullable": True},
    )
    assert res.status_code == 201

    col_names = [
        c["name"]
        for t in client.get(f"/api/connections/{mem_conn}/tables").json()
        for c in t["columns"]
    ]
    assert "email" in col_names

    res = client.delete(f"/api/connections/{mem_conn}/tables/users/columns/email")
    assert res.status_code == 200


def test_row_crud(client, mem_conn):
    _create_table(client, mem_conn)

    res = client.post(
        f"/api/connections/{mem_conn}/tables/users/rows",
        json={"data": {"id": 1, "name": "Ada", "age": 37}},
    )
    assert res.status_code == 201
    client.post(
        f"/api/connections/{mem_conn}/tables/users/rows",
        json={"data": {"id": 2, "name": "Bob", "age": 40}},
    )

    rows_res = client.get(f"/api/connections/{mem_conn}/tables/users/rows")
    assert rows_res.status_code == 200
    body = rows_res.json()
    assert body["columns"] == ["id", "name", "age", "created_at", "updated_at"]
    assert len(body["rows"]) == 2

    res = client.put(
        f"/api/connections/{mem_conn}/tables/users/rows",
        json={"data": {"age": 38}, "pk": {"id": 1}},
    )
    assert res.status_code == 200

    rows = client.get(f"/api/connections/{mem_conn}/tables/users/rows").json()["rows"]
    ada = next(r for r in rows if r["name"] == "Ada")
    assert ada["age"] == 38

    res = client.request(
        "DELETE",
        f"/api/connections/{mem_conn}/tables/users/rows",
        content=json.dumps({"data": {}, "pk": {"id": 2}}),
        headers={"content-type": "application/json"},
    )
    assert res.status_code == 200
    rows = client.get(f"/api/connections/{mem_conn}/tables/users/rows").json()["rows"]
    assert len(rows) == 1


def test_update_requires_pk(client, mem_conn):
    _create_table(client, mem_conn)
    res = client.put(
        f"/api/connections/{mem_conn}/tables/users/rows",
        json={"data": {"age": 1}},
    )
    assert res.status_code == 422


def test_run_sql(client, mem_conn):
    _create_table(client, mem_conn)
    client.post(
        f"/api/connections/{mem_conn}/tables/users/rows",
        json={"data": {"id": 1, "name": "Ada", "age": 37}},
    )

    res = client.post(
        f"/api/connections/{mem_conn}/sql",
        json={"statement": "SELECT name, age FROM users WHERE age = :age", "params": {"age": 37}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["columns"] == ["name", "age"]
    assert body["rows"] == [["Ada", 37]]


def test_run_sql_error(client, mem_conn):
    res = client.post(
        f"/api/connections/{mem_conn}/sql",
        json={"statement": "SELECT * FROM missing_table"},
    )
    assert res.status_code == 400


def test_generate_select_sql(client, mem_conn):
    _create_table(client, mem_conn)
    res = client.post(
        f"/api/connections/{mem_conn}/generate",
        json={
            "table": "users",
            "verb": "select",
            "columns": ["id", "name"],
            "eq": {"age": 37},
            "page": 2,
            "page_size": 10,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["sql"] == (
        'SELECT "id", "name" FROM "users" WHERE "age" = :__f0 '
        'LIMIT :__f1 OFFSET :__f2;'
    )
    assert body["params"] == {"__f0": 37, "__f1": 10, "__f2": 10}


def test_generate_all_verbs(client, mem_conn):
    _create_table(client, mem_conn)
    body = {
        "table": "users",
        "verb": "upsert",
        "data": {"id": 1, "name": "Ada"},
        "conflict_columns": ["id"],
    }
    res = client.post(f"/api/connections/{mem_conn}/generate", json=body)
    assert res.status_code == 200
    assert "ON CONFLICT" in res.json()["sql"]

    body["verb"] = "insert"
    res = client.post(f"/api/connections/{mem_conn}/generate", json=body)
    assert res.json()["sql"].startswith('INSERT INTO "users"')

    body["verb"] = "update"
    body["pk"] = {"id": 1}
    res = client.post(f"/api/connections/{mem_conn}/generate", json=body)
    assert res.json()["sql"].startswith('UPDATE "users"')

    body["verb"] = "delete"
    res = client.post(f"/api/connections/{mem_conn}/generate", json=body)
    assert res.json()["sql"].startswith('DELETE FROM "users"')

    body["verb"] = "count"
    res = client.post(f"/api/connections/{mem_conn}/generate", json=body)
    assert res.json()["sql"].startswith('SELECT COUNT(*) AS count')


def test_generate_bad_options_400(client, mem_conn):
    res = client.post(
        f"/api/connections/{mem_conn}/generate",
        json={"table": "users", "verb": "select", "offset": 10},
    )
    assert res.status_code == 400


def test_drop_table(client, mem_conn):
    _create_table(client, mem_conn)
    res = client.delete(f"/api/connections/{mem_conn}/tables/users")
    assert res.status_code == 204
    names = [t["name"] for t in client.get(f"/api/connections/{mem_conn}/tables").json()]
    assert "users" not in names


def test_unknown_connection_404(client):
    assert client.get("/api/connections/nope/tables").status_code == 404
    assert client.delete("/api/connections/nope/tables/users").status_code == 404


def test_create_and_list_indexes(client, mem_conn):
    _create_table(client, mem_conn)
    res = client.post(
        f"/api/connections/{mem_conn}/tables/users/indexes",
        json={"name": "idx_users_name", "columns": ["name"], "unique": False},
    )
    assert res.status_code == 201, res.text

    indexes = client.get(f"/api/connections/{mem_conn}/tables/users/indexes").json()
    assert any(i["name"] == "idx_users_name" and i["columns"] == ["name"] for i in indexes)

    res = client.delete(
        f"/api/connections/{mem_conn}/tables/users/indexes/idx_users_name"
    )
    assert res.status_code == 204
    assert client.get(f"/api/connections/{mem_conn}/tables/users/indexes").json() == []


def test_create_index_bad_table_404(client, mem_conn):
    res = client.post(
        f"/api/connections/{mem_conn}/tables/missing/indexes",
        json={"name": "i1", "columns": ["id"]},
    )
    assert res.status_code == 404


def test_create_index_duplicate_conflict(client, mem_conn):
    _create_table(client, mem_conn)
    body = {"name": "idx_users_name", "columns": ["name"]}
    assert client.post(f"/api/connections/{mem_conn}/tables/users/indexes", json=body).status_code == 201
    res = client.post(f"/api/connections/{mem_conn}/tables/users/indexes", json=body)
    assert res.status_code == 400


def test_views_roundtrip(client, mem_conn):
    _create_table(client, mem_conn)
    client.post(
        f"/api/connections/{mem_conn}/tables/users/rows",
        json={"data": {"id": 1, "name": "Ada", "age": 37}},
    )
    res = client.post(
        f"/api/connections/{mem_conn}/sql",
        json={"statement": "CREATE VIEW user_names AS SELECT name, age FROM users"},
    )
    assert res.status_code == 200, res.text

    assert client.get(f"/api/connections/{mem_conn}/views").json() == ["user_names"]

    body = client.get(f"/api/connections/{mem_conn}/views/user_names/rows").json()
    assert body["columns"] == ["name", "age"]
    assert body["rows"] == [{"name": "Ada", "age": 37}]


# ------------------------------------------------------------------- foreign keys
def _fk_table(client, conn_id, name="posts"):
    res = client.post(
        f"/api/connections/{conn_id}/tables",
        json={
            "name": name,
            "columns": [
                {"name": "id", "data_type": "INTEGER", "primary_key": True, "nullable": False},
                {"name": "user_id", "data_type": "INTEGER", "nullable": True},
            ],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_create_foreign_key_sqlite_generated_name(client, mem_conn):
    _create_table(client, mem_conn)
    _fk_table(client, mem_conn)
    res = client.post(
        f"/api/connections/{mem_conn}/tables/posts/foreign_keys",
        json={
            "columns": ["user_id"],
            "referred_table": "users",
            "referred_columns": ["id"],
            "on_delete": "CASCADE",
        },
    )
    assert res.status_code == 201, res.text

    rel = client.get(f"/api/connections/{mem_conn}/tables/posts/relationships").json()
    assert len(rel["outbound"]) == 1
    fk = rel["outbound"][0]
    assert fk["name"].startswith("fk_posts_users_")
    assert fk["columns"] == ["user_id"]
    assert fk["referred_table"] == "users"
    assert fk["referred_columns"] == ["id"]
    assert fk["on_delete"] == "CASCADE"
    assert fk["cardinality"] == "N:1"

    # users sees the inbound reference
    rel_users = client.get(f"/api/connections/{mem_conn}/tables/users/relationships").json()
    assert len(rel_users["inbound"]) == 1
    assert rel_users["inbound"][0]["table"] == "posts"


def test_foreign_key_1to1_cardinality(client, mem_conn):
    _create_table(client, mem_conn)
    _fk_table(client, mem_conn)
    # user_id is not the PK -> N:1; make a second table where the FK is the PK
    client.post(
        f"/api/connections/{mem_conn}/tables",
        json={
            "name": "profiles",
            "columns": [
                {"name": "user_id", "data_type": "INTEGER", "primary_key": True, "nullable": False},
            ],
        },
    )
    res = client.post(
        f"/api/connections/{mem_conn}/tables/profiles/foreign_keys",
        json={"columns": ["user_id"], "referred_table": "users", "referred_columns": ["id"]},
    )
    assert res.status_code == 201, res.text
    rel = client.get(f"/api/connections/{mem_conn}/tables/profiles/relationships").json()
    assert rel["outbound"][0]["cardinality"] == "1:1"
    # users side sees a 1:1 inbound
    rel_users = client.get(f"/api/connections/{mem_conn}/tables/users/relationships").json()
    assert rel_users["inbound"][0]["cardinality"] == "1:1"


def test_drop_foreign_key_sqlite(client, mem_conn):
    _create_table(client, mem_conn)
    _fk_table(client, mem_conn)
    name = f"fk_posts_users_user_id"
    body = {"name": name, "columns": ["user_id"], "referred_table": "users", "referred_columns": ["id"]}
    assert client.post(f"/api/connections/{mem_conn}/tables/posts/foreign_keys", json=body).status_code == 201
    assert len(client.get(f"/api/connections/{mem_conn}/tables/posts/relationships").json()["outbound"]) == 1

    res = client.delete(f"/api/connections/{mem_conn}/tables/posts/foreign_keys/{name}")
    assert res.status_code == 204
    rel = client.get(f"/api/connections/{mem_conn}/tables/posts/relationships").json()
    assert rel["outbound"] == []


def test_foreign_key_rebuild_preserves_data_and_indexes(client, mem_conn):
    _create_table(client, mem_conn)
    _fk_table(client, mem_conn)
    client.post(
        f"/api/connections/{mem_conn}/tables/posts/rows",
        json={"data": {"id": 1, "user_id": 1}},
    )
    client.post(
        f"/api/connections/{mem_conn}/tables/posts/indexes",
        json={"name": "idx_posts_user", "columns": ["user_id"]},
    )
    res = client.post(
        f"/api/connections/{mem_conn}/tables/posts/foreign_keys",
        json={"columns": ["user_id"], "referred_table": "users", "referred_columns": ["id"]},
    )
    assert res.status_code == 201, res.text

    rows = client.get(f"/api/connections/{mem_conn}/tables/posts/rows").json()
    assert len(rows["rows"]) == 1
    assert rows["rows"][0]["id"] == 1
    assert rows["rows"][0]["user_id"] == 1
    indexes = client.get(f"/api/connections/{mem_conn}/tables/posts/indexes").json()
    assert any(i["name"] == "idx_posts_user" for i in indexes)


def test_many_to_many_junction(client, mem_conn):
    _create_table(client, mem_conn)
    _fk_table(client, mem_conn, "posts")
    client.post(
        f"/api/connections/{mem_conn}/tables",
        json={
            "name": "tags",
            "columns": [
                {"name": "id", "data_type": "INTEGER", "primary_key": True, "nullable": False},
            ],
        },
    )
    # junction with composite primary key covering both FKs
    client.post(
        f"/api/connections/{mem_conn}/tables",
        json={
            "name": "post_tags",
            "columns": [
                {"name": "post_id", "data_type": "INTEGER", "primary_key": True, "nullable": False},
                {"name": "tag_id", "data_type": "INTEGER", "primary_key": True, "nullable": False},
            ],
        },
    )
    for ref in (("post_id", "posts"), ("tag_id", "tags")):
        res = client.post(
            f"/api/connections/{mem_conn}/tables/post_tags/foreign_keys",
            json={"columns": [ref[0]], "referred_table": ref[1], "referred_columns": ["id"]},
        )
        assert res.status_code == 201, res.text

    rel = client.get(f"/api/connections/{mem_conn}/tables/posts/relationships").json()
    assert rel["many_to_many"] == [{"endpoint": "tags", "through": "post_tags"}]
    assert rel["junction"] is False

    junction = client.get(f"/api/connections/{mem_conn}/tables/post_tags/relationships").json()
    assert junction["junction"] is True
    assert {m["endpoint"] for m in junction["many_to_many"]} == {"posts", "tags"}


def test_foreign_key_bad_length_400(client, mem_conn):
    _create_table(client, mem_conn)
    res = client.post(
        f"/api/connections/{mem_conn}/tables/users/foreign_keys",
        json={"columns": ["id"], "referred_table": "users", "referred_columns": ["id", "name"]},
    )
    assert res.status_code == 400


def test_relationships_missing_table_404(client, mem_conn):
    assert client.get(f"/api/connections/{mem_conn}/tables/nope/relationships").status_code == 404