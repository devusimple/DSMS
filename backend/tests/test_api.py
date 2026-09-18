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
    assert body["columns"] == ["id", "name", "age"]
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


def test_drop_table(client, mem_conn):
    _create_table(client, mem_conn)
    res = client.delete(f"/api/connections/{mem_conn}/tables/users")
    assert res.status_code == 204
    names = [t["name"] for t in client.get(f"/api/connections/{mem_conn}/tables").json()]
    assert "users" not in names


def test_unknown_connection_404(client):
    assert client.get("/api/connections/nope/tables").status_code == 404
    assert client.delete("/api/connections/nope/tables/users").status_code == 404