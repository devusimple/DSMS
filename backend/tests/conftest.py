import pytest
from api.db.manager import manager
from api.main import app
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_connections():
    """Ensure live engines are disposed between tests."""
    yield
    for conn_id in list(manager.list()):
        manager.close(conn_id.id)


@pytest.fixture()
def mem_conn(client):
    """Create an in-memory SQLite connection and return its id."""
    res = client.post(
        "/api/connections",
        json={"name": "mem", "dialect": "sqlite"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]
