# DSMS – Database Schema Management System

Web app for visually creating/managing database schemas: CRUD on tables, rows, and columns across SQLite, PostgreSQL, and MySQL, with runtime-configurable database connections.

## Stack

- Backend: Python 3.13 + FastAPI, SQLAlchemy 2.x as the DB abstraction layer, uvicorn. Runtime connections use `psycopg` (PostgreSQL) and `pymysql` (MySQL); no other drivers.
- Frontend: React + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui (Radix-based, manual components in `src/components/ui/`).
- Tests: pytest (backend) — run from `backend/` with `.venv\Scripts\python -m pytest`.

## Layout

- `backend/app/sqlgen.py` – pure SQL generation (DDL + parameterized DML). Isolated from connection management by design.
- `backend/app/db/manager.py` – in-process registry of live SQLAlchemy engines; user-supplied connections only, never persisted.
- `backend/app/db/ops.py` – reflection helpers (list tables, reflect table, fetch rows).
- `backend/app/routers/` – `connections`, `tables`, `columns`, `rows`, `sql`.
- `frontend/src/lib/api.ts` + `types.ts` – typed API client mirroring backend response models; keep in sync.
- `frontend/src/` – `App.tsx` (layout), `CreateConnectionDialog`, `SchemaView`, `TableDetail` (Columns/Rows/SQL tabs), `RowEditorDialog`, `CreateTableDialog`.

## Commands

- Backend dev: from `backend/` → `.venv\Scripts\python -m uvicorn app.main:app --reload` (port 8000)
- Backend tests: from `backend/` → `.venv\Scripts\python -m pytest -q`
- Frontend dev: from `frontend/` → `bun run dev` (port 5173; `/api/*` is Vite-proxied to 127.0.0.1:8000)
- Frontend build/typecheck: `bun run build` (runs `tsc -b` then `vite build`)

## Conventions / gotchas

- All DB access goes through SQLAlchemy — no direct psycopg2/mysql-connector/sqlite3 imports outside the abstraction layer. Write portable SQL; avoid dialect-specific syntax in shared code. Tests run against SQLite at minimum.
- DB connections are supplied by the user at runtime (DSN or per-dialect components). Never hardcode or commit credentials. `manager.create()` persists engines in memory only (process lifetime).
- User-supplied schema SQL is generated UI output; SQL generation stays isolated in `sqlgen.py`, separate from connection management.
- DML is executed via generated SQL with bound parameters (`:__c0`-style), never with inlined values.
- API error responses carry `detail` (string) — frontend `api.ts` surfaces it.
- Use `bun` for all frontend package work, not npm (extremely slow on this machine).
- Cannot rely on pip downloads being fast here; backend deps are pinned in `backend/requirements.txt` and installed into `backend/.venv`.
- SQLite in-memory connections use SQLAlchemy `StaticPool` + `check_same_thread: false` so FastAPI's threadpool and shared engines work (see `manager.py`).

## Conventions / gotchas

- All DB access goes through SQLAlchemy — no direct psycopg2/mysql-connector/sqlite3 imports outside the abstraction layer. Write portable SQL; avoid dialect-specific syntax in shared code. Tests should run against SQLite at minimum.
- DB connections are supplied by the user at runtime (DSN/driver selection per target database). Never hardcode or commit credentials.
- User-supplied schema SQL is generated UI output; keep SQL generation isolated in its own module from connection management.