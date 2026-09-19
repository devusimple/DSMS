"""DSMS FastAPI application entrypoint.

Run from backend/::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import columns, connections, foreign_keys, indexes, rows, sql, tables, views

app = FastAPI(title="DSMS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    connections.router,
    tables.router,
    columns.router,
    indexes.router,
    foreign_keys.router,
    rows.router,
    sql.router,
    views.router,
):
    app.include_router(router, prefix="/api", tags=[router.prefix or "api"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}