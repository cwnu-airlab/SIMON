"""Async SQLite connection manager using aiosqlite.

Configures WAL mode, busy timeout, and foreign keys.
Auto-creates tables on first connection.
"""

import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    revoked_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New Chat',
    system_prompt TEXT DEFAULT '',
    model_params TEXT
        DEFAULT '{"temperature":0.7,"max_tokens":4096,"top_p":0.9,"enable_thinking":true}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
"""


async def _column_exists(
    db: aiosqlite.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    rows = await cursor.fetchall()
    return any(row[1] == column_name for row in rows)


async def _run_migrations(db: aiosqlite.Connection) -> None:
    if not await _column_exists(db, "conversations", "user_id"):
        _ = await db.execute(
            "ALTER TABLE conversations ADD COLUMN user_id TEXT "
            + "REFERENCES users(id) ON DELETE CASCADE",
        )
    _ = await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversations_user_updated_at "
        + "ON conversations(user_id, updated_at DESC)",
    )
    _ = await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
    _ = await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)")


@contextlib.asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Open a database connection with pragmas configured.

    Usage::

        async with get_db() as db:
            cursor = await db.execute("SELECT ...")
    """
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        _ = await db.execute("PRAGMA journal_mode=WAL")
        _ = await db.execute("PRAGMA busy_timeout=5000")
        _ = await db.execute("PRAGMA foreign_keys=ON")
        yield db


async def init_db() -> None:
    """Initialize database: create directory, tables, and set WAL mode."""
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(settings.database_path) as db:
        _ = await db.execute("PRAGMA journal_mode=WAL")
        _ = await db.execute("PRAGMA busy_timeout=5000")
        _ = await db.execute("PRAGMA foreign_keys=ON")
        _ = await db.executescript(SCHEMA_SQL)
        await _run_migrations(db)
        await db.commit()

    logger.info("Database initialized at %s", settings.database_path)
