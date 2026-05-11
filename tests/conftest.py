"""Pytest fixtures for testcontainers-based PostgreSQL integration tests.

Lifecycle:
- Session-scoped ``pg_dsn`` starts a single Postgres 16 container, exports
  ``DATABASE_URL``, applies ``SCHEMA_SQL`` once, and tears down on exit.
- Per-test ``_pg_isolation`` autouse fixture TRUNCATEs every table with
  ``RESTART IDENTITY CASCADE`` so every test starts from a known state, and
  monkeypatches ``app.database.get_db`` (and the re-export in
  ``app.services.database``) to open a fresh ``asyncpg.connect`` per call.

The per-call connection override sidesteps asyncio event-loop binding:
unittest's ``setUp`` and each test method invoke ``asyncio.run`` separately, so
a long-lived ``asyncpg.Pool`` would fail when used across loops. The override
preserves the ``async with get_db() as conn`` interface used everywhere in
``app/services/database.py`` while making each call self-contained.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest
from testcontainers.postgres import PostgresContainer


def _normalize_dsn(dsn: str) -> str:
    # testcontainers may emit `postgresql+psycopg2://…` style; asyncpg wants `postgresql://`.
    if dsn.startswith("postgresql+"):
        return "postgresql://" + dsn.split("://", 1)[1]
    return dsn


@pytest.fixture(scope="session")
def pg_dsn() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine") as pg:
        dsn = _normalize_dsn(pg.get_connection_url(driver=None))
        os.environ["DATABASE_URL"] = dsn
        # Force settings to pick up the new URL the next time it's imported.
        import app.config

        app.config.settings.database_url = dsn

        # Apply schema once. Subsequent tests just truncate.
        async def _init() -> None:
            from app.database import SCHEMA_SQL, _run_migrations

            conn = await asyncpg.connect(dsn=dsn)
            try:
                await conn.execute(SCHEMA_SQL)
                await _run_migrations(conn)
            finally:
                await conn.close()

        asyncio.run(_init())
        yield dsn


@pytest.fixture(autouse=True)
def _pg_isolation(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Truncate tables and override ``get_db`` for the lifetime of one test."""

    async def _truncate() -> None:
        conn = await asyncpg.connect(dsn=pg_dsn)
        try:
            await conn.execute(
                "TRUNCATE TABLE attachments, messages, conversations, "
                "api_keys, sessions, users RESTART IDENTITY CASCADE"
            )
        finally:
            await conn.close()

    asyncio.run(_truncate())

    @contextlib.asynccontextmanager
    async def _per_call_get_db() -> AsyncIterator[asyncpg.Connection]:
        conn = await asyncpg.connect(dsn=pg_dsn)
        try:
            yield conn
        finally:
            await conn.close()

    import app.database
    import app.services.database

    monkeypatch.setattr(app.database, "get_db", _per_call_get_db)
    monkeypatch.setattr(app.services.database, "get_db", _per_call_get_db)
    yield
