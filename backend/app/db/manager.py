"""Runtime database connection management.

Users supply connection details at runtime (DSN or component fields);
we build SQLAlchemy engines on demand and keep them in an in-process
registry keyed by connection id. Nothing here hardcodes credentials.

Only sqlite/postgresql/mysql are supported. All DML/DDL execution goes
through SQLAlchemy; no raw driver code outside this module.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass

from sqlalchemy import URL, create_engine, make_url
from sqlalchemy.engine import Engine

from app.schemas import Dialect


@dataclass
class ConnectionSpec:
    """Normalized connection spec extracted from the API payload."""

    name: str
    dialect: Dialect
    dsn: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    file: str | None = None


@dataclass
class ConnectionRecord:
    id: str
    name: str
    dialect: Dialect
    engine: Engine
    url_display: str


class ConnectionFailed(RuntimeError):
    """Raised when a connection cannot be created or reached."""


def _build_url(spec: ConnectionSpec) -> URL:
    if spec.dsn:
        return make_url(spec.dsn)

    if spec.dialect == "sqlite":
        path = spec.file or spec.database or ":memory:"
        return URL.create("sqlite+pysqlite", database=path)

    driver = "psycopg" if spec.dialect == "postgresql" else "pymysql"
    host = spec.host or "localhost"
    port = spec.port or _DEFAULT_PORTS[spec.dialect]
    database = spec.database or ""
    if not database:
        raise ConnectionFailed("database name is required")
    return URL.create(
        f"{spec.dialect}+{driver}",
        host=host,
        port=port,
        database=database,
        username=spec.username,
        password=spec.password,
    )


_DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306}


def _engine_from_url(url: URL) -> Engine:
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        from sqlalchemy.pool import StaticPool

        # FastAPI runs sync handlers in a threadpool; allow the engine's
        # single in-memory connection to be handed across threads. In-memory
        # SQLite also needs a shared pool so every request sees the same db.
        kwargs.update(
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(url, **kwargs)


class ConnectionManager:
    """Owns live engines. Thread-safe for FastAPI's threadpool."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, ConnectionRecord] = {}

    def create(self, spec: ConnectionSpec) -> ConnectionRecord:
        url = _build_url(spec)
        engine = _engine_from_url(url)
        try:
            with engine.connect():
                pass
        except Exception as exc:  # noqa: BLE001 - surface any driver error
            engine.dispose()
            raise ConnectionFailed(f"{spec.name}: {exc}") from exc

        record = ConnectionRecord(
            id=uuid.uuid4().hex,
            name=spec.name,
            dialect=spec.dialect,
            engine=engine,
            url_display=url.render_as_string(hide_password=True),
        )
        with self._lock:
            self._records[record.id] = record
        return record

    def get(self, conn_id: str) -> ConnectionRecord:
        with self._lock:
            record = self._records.get(conn_id)
        if record is None:
            raise KeyError(f"Unknown connection id {conn_id!r}")
        return record

    def list(self) -> list[ConnectionRecord]:
        with self._lock:
            return list(self._records.values())

    def close(self, conn_id: str) -> bool:
        with self._lock:
            record = self._records.pop(conn_id, None)
        if record is None:
            return False
        record.engine.dispose()
        return True


manager = ConnectionManager()