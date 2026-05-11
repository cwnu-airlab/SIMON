"""One-time migration: SQLite chat.db → PostgreSQL.

Usage:
    python scripts/migrate_sqlite_to_pg.py --src data/chat.db --dst-dsn $DATABASE_URL
    python scripts/migrate_sqlite_to_pg.py --src data/chat.db --dst-dsn $DATABASE_URL --dry-run
    python scripts/migrate_sqlite_to_pg.py \\
        --src data/chat.db --dst-dsn $DATABASE_URL --truncate-first

Behavior:
- Reads the SQLite file with the stdlib sqlite3 module (read-only).
- Writes to PostgreSQL via asyncpg using the SAME schema layout as
  app.database.SCHEMA_SQL (CITEXT username, BIGINT IDENTITY ids, TIMESTAMPTZ
  timestamps).
- INSERTs are idempotent: ``ON CONFLICT (id) DO NOTHING`` so re-running with the
  same source produces no duplicates.
- ISO 8601 timestamp strings from SQLite are parsed into ``datetime`` and bound
  to TIMESTAMPTZ columns; missing/empty strings are passed as ``None``.
- After all inserts, IDENTITY sequences for ``messages.id`` and
  ``attachments.id`` are advanced past the imported max so subsequent inserts
  don't collide.
- ``--dry-run`` prints what would be inserted but skips writes.
- ``--truncate-first`` clears the destination tables before inserting (useful
  for repeatable rehearsals against a non-empty PG).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import asyncpg

logger = logging.getLogger("migrate_sqlite_to_pg")


# Tables in FK-safe insertion order. children must come AFTER parents.
TABLE_ORDER: tuple[str, ...] = (
    "users",
    "sessions",
    "api_keys",
    "conversations",
    "messages",
    "attachments",
)


# Columns to copy per table. Excludes columns that don't exist in legacy SQLite
# rows (the new VLM image columns are filled with NULL/defaults via the schema).
TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "users": ("id", "username", "password_hash", "password_salt", "created_at"),
    "sessions": ("id", "user_id", "expires_at", "created_at"),
    "api_keys": (
        "id",
        "user_id",
        "name",
        "key_hash",
        "key_prefix",
        "created_at",
        "last_used_at",
        "revoked_at",
    ),
    "conversations": (
        "id",
        "user_id",
        "title",
        "system_prompt",
        "model_params",
        "created_at",
        "updated_at",
    ),
    "messages": (
        "id",
        "conversation_id",
        "role",
        "content",
        "reasoning",
        "created_at",
    ),
    "attachments": (
        "id",
        "conversation_id",
        "message_id",
        "filename",
        "file_hash",
        "pages",
        "markdown_content",
        "file_path",
        "attachment_type",
        "mime_type",
        "width",
        "height",
        "byte_size",
        "created_at",
    ),
}

# Columns that should be coerced from ISO string to datetime when present.
TIMESTAMP_COLUMNS = frozenset(
    {"created_at", "updated_at", "expires_at", "last_used_at", "revoked_at"}
)

# Tables whose primary key is an IDENTITY sequence. After importing, advance
# the sequence so subsequent inserts don't collide.
IDENTITY_TABLES: tuple[str, ...] = ("messages", "attachments")


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # SQLite stores 'YYYY-MM-DD HH:MM:SS' by default for DEFAULT
        # CURRENT_TIMESTAMP. Python's fromisoformat accepts the space form
        # since 3.11. ISO with 'T' is also handled.
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            logger.warning("could not parse timestamp %r — using NULL", s)
            return None
    return None


def _row_value(table: str, column: str, raw: object) -> object:
    if column in TIMESTAMP_COLUMNS:
        return _parse_timestamp(raw)
    return raw


def _read_table(
    sqlite_conn: sqlite3.Connection, table: str
) -> Iterable[tuple[object, ...]]:
    cols = TABLE_COLUMNS[table]
    # Probe which of these actually exist in the source schema (legacy DBs may
    # be missing the newer attachment columns).
    existing = {row[1] for row in sqlite_conn.execute(f"PRAGMA table_info({table})")}
    select_cols = [c if c in existing else f"NULL AS {c}" for c in cols]
    sql = f"SELECT {', '.join(select_cols)} FROM {table}"  # noqa: S608 — internal table list
    cursor = sqlite_conn.execute(sql)
    for raw_row in cursor:
        yield tuple(_row_value(table, col, raw_row[i]) for i, col in enumerate(cols))


def _build_insert(table: str) -> str:
    cols = TABLE_COLUMNS[table]
    placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
    return (
        f"INSERT INTO {table} ({', '.join(cols)}) "  # noqa: S608
        f"VALUES ({placeholders}) "
        f"ON CONFLICT (id) DO NOTHING"
    )


async def _truncate_all(pg: asyncpg.Connection) -> None:
    # CASCADE so FKs from messages/attachments don't block clearing parents.
    _ = await pg.execute(
        "TRUNCATE TABLE attachments, messages, conversations, api_keys, "
        "sessions, users RESTART IDENTITY CASCADE"
    )


async def _advance_identity_sequences(pg: asyncpg.Connection) -> None:
    for table in IDENTITY_TABLES:
        _ = await pg.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                (SELECT MAX(id) FROM {table}) IS NOT NULL
            )
            """
        )


async def migrate(
    src: Path,
    dst_dsn: str,
    *,
    dry_run: bool,
    truncate_first: bool,
) -> dict[str, int]:
    if not src.exists():
        raise FileNotFoundError(f"SQLite source not found: {src}")

    counts: dict[str, int] = {}
    sqlite_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        if dry_run:
            for table in TABLE_ORDER:
                rows = list(_read_table(sqlite_conn, table))
                counts[table] = len(rows)
                logger.info("[dry-run] %s: would insert %d rows", table, len(rows))
            return counts

        pg = await asyncpg.connect(dsn=dst_dsn)
        try:
            async with pg.transaction():
                if truncate_first:
                    logger.info("TRUNCATE all tables (--truncate-first)")
                    await _truncate_all(pg)
                for table in TABLE_ORDER:
                    insert_sql = _build_insert(table)
                    rows = list(_read_table(sqlite_conn, table))
                    if rows:
                        await pg.executemany(insert_sql, rows)
                    counts[table] = len(rows)
                    logger.info("%s: inserted up to %d rows", table, len(rows))
                await _advance_identity_sequences(pg)
                logger.info("identity sequences advanced past imported max")
        finally:
            await pg.close()
    finally:
        sqlite_conn.close()

    return counts


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate a SQLite chat.db into PostgreSQL.",
    )
    parser.add_argument(
        "--src",
        type=Path,
        required=True,
        help="Path to the SQLite source database.",
    )
    parser.add_argument(
        "--dst-dsn",
        required=True,
        help="postgresql://user:pass@host:port/db DSN of the destination.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read source, count rows, but do NOT write to PG.",
    )
    parser.add_argument(
        "--truncate-first",
        action="store_true",
        help="TRUNCATE destination tables before inserting (use for rehearsals).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    counts = asyncio.run(
        migrate(
            src=args.src,
            dst_dsn=args.dst_dsn,
            dry_run=args.dry_run,
            truncate_first=args.truncate_first,
        )
    )
    total = sum(counts.values())
    label = "[dry-run] would migrate" if args.dry_run else "migrated"
    logger.info("%s %d total rows: %s", label, total, counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
