"""CRUD operations for users, sessions, API keys, conversations, messages, attachments.

This module is the only place that talks to PostgreSQL. The rest of the
application catches the abstract exceptions defined here (`IntegrityViolation`,
`NotFound`) so callers stay driver-agnostic.

asyncpg conventions used throughout:
- Parameters are positional ($1, $2, …) — no named placeholders.
- INSERT statements use ``RETURNING`` to fetch generated identity / row state
  in a single round-trip.
- Result rows are ``asyncpg.Record`` instances; we convert to plain dicts via
  ``_row_to_dict`` so the rest of the codebase keeps using ``dict[str, object]``.
- Auto-commit is the default; explicit transactions are entered with
  ``async with conn.transaction():`` only where multiple statements need to
  share atomicity (``add_message``, ``add_attachment``, ``add_image_attachment``).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import cast

import asyncpg

from app.config import settings
from app.database import get_db

RowDict = dict[str, object]


class IntegrityViolation(RuntimeError):
    """Raised on unique / foreign-key / check violations.

    Driver-agnostic abstraction over asyncpg's
    ``UniqueViolationError`` / ``ForeignKeyViolationError`` /
    ``CheckViolationError`` /
    raised explicitly when an ownership pre-check fails (e.g. a conversation
    does not belong to the calling user).
    """


class NotFound(RuntimeError):
    """Raised when a row that must exist could not be located."""


def _row_to_dict(row: asyncpg.Record | None) -> RowDict | None:
    return dict(row) if row is not None else None


def _rows_to_dicts(rows: list[asyncpg.Record]) -> list[RowDict]:
    return [dict(row) for row in rows]


def _affected_row_count(status: str) -> int:
    """Parse asyncpg's command-status string ('UPDATE 3', 'DELETE 0', ...)."""
    if not status:
        return 0
    parts = status.split()
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0


def _wrap_pg_error(exc: Exception) -> Exception:
    """Translate known asyncpg errors into our abstract exceptions."""
    if isinstance(
        exc,
        (
            asyncpg.exceptions.UniqueViolationError,
            asyncpg.exceptions.ForeignKeyViolationError,
            asyncpg.exceptions.CheckViolationError,
            asyncpg.exceptions.NotNullViolationError,
        ),
    ):
        return IntegrityViolation(str(exc))
    return exc


async def _purge_expired_revoked_api_keys(conn: asyncpg.Connection) -> None:
    minutes = settings.api_key_revocation_retention_minutes
    _ = await conn.execute(
        "DELETE FROM api_keys "
        "WHERE revoked_at IS NOT NULL "
        "AND revoked_at <= NOW() - make_interval(mins => $1)",
        minutes,
    )


async def create_user(
    username: str,
    password_hash: str,
    password_salt: str,
) -> RowDict:
    user_id = uuid.uuid4().hex
    async with get_db() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO users (id, username, password_hash, password_salt) "
                "VALUES ($1, $2, $3, $4) RETURNING *",
                user_id,
                username,
                password_hash,
                password_salt,
            )
        except asyncpg.exceptions.PostgresError as exc:
            raise _wrap_pg_error(exc) from exc
        if row is None:
            raise RuntimeError("Failed to create user")
        return dict(row)


async def get_user_by_username(username: str) -> RowDict | None:
    async with get_db() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
        return _row_to_dict(row)


async def create_session(session_id: str, user_id: str, expires_at: datetime) -> None:
    async with get_db() as conn:
        try:
            _ = await conn.execute(
                "INSERT INTO sessions (id, user_id, expires_at) VALUES ($1, $2, $3)",
                session_id,
                user_id,
                expires_at,
            )
        except asyncpg.exceptions.PostgresError as exc:
            raise _wrap_pg_error(exc) from exc


async def create_api_key(user_id: str, name: str, key_hash: str, key_prefix: str) -> RowDict:
    api_key_id = uuid.uuid4().hex
    async with get_db() as conn:
        try:
            async with conn.transaction():
                await _purge_expired_revoked_api_keys(conn)
                row = await conn.fetchrow(
                    "INSERT INTO api_keys (id, user_id, name, key_hash, key_prefix) "
                    "VALUES ($1, $2, $3, $4, $5) RETURNING *",
                    api_key_id,
                    user_id,
                    name,
                    key_hash,
                    key_prefix,
                )
        except asyncpg.exceptions.PostgresError as exc:
            raise _wrap_pg_error(exc) from exc
        if row is None:
            raise RuntimeError("Failed to create API key")
        return dict(row)


async def list_api_keys(user_id: str) -> list[RowDict]:
    async with get_db() as conn:
        await _purge_expired_revoked_api_keys(conn)
        rows = await conn.fetch(
            "SELECT * FROM api_keys WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
        return _rows_to_dicts(rows)


async def revoke_api_key(user_id: str, api_key_id: str) -> bool:
    async with get_db() as conn:
        async with conn.transaction():
            await _purge_expired_revoked_api_keys(conn)
            status = await conn.execute(
                "UPDATE api_keys SET revoked_at = NOW() "
                "WHERE user_id = $1 AND id = $2 AND revoked_at IS NULL",
                user_id,
                api_key_id,
            )
        return _affected_row_count(status) > 0


async def get_api_key_user(key_hash: str) -> RowDict | None:
    async with get_db() as conn:
        async with conn.transaction():
            await _purge_expired_revoked_api_keys(conn)
            row = await conn.fetchrow(
                """
                SELECT api_keys.id AS api_key_id, users.id, users.username, users.created_at
                FROM api_keys
                JOIN users ON users.id = api_keys.user_id
                WHERE api_keys.key_hash = $1 AND api_keys.revoked_at IS NULL
                """,
                key_hash,
            )
            if row is None:
                return None
            _ = await conn.execute(
                "UPDATE api_keys SET last_used_at = NOW() WHERE key_hash = $1",
                key_hash,
            )
        return dict(row)


async def get_session_user(session_id: str) -> RowDict | None:
    async with get_db() as conn:
        row = await conn.fetchrow(
            """
            SELECT sessions.user_id, sessions.expires_at, users.username, users.created_at
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.id = $1
            """,
            session_id,
        )
        return _row_to_dict(row)


async def delete_session(session_id: str) -> bool:
    async with get_db() as conn:
        status = await conn.execute("DELETE FROM sessions WHERE id = $1", session_id)
        return _affected_row_count(status) > 0


async def create_conversation(user_id: str) -> RowDict:
    conv_id = uuid.uuid4().hex
    async with get_db() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO conversations (id, user_id) VALUES ($1, $2) RETURNING *",
                conv_id,
                user_id,
            )
        except asyncpg.exceptions.PostgresError as exc:
            raise _wrap_pg_error(exc) from exc
        if row is None:
            raise RuntimeError("Failed to create conversation")
        return dict(row)


async def list_conversations(user_id: str) -> list[RowDict]:
    async with get_db() as conn:
        rows = await conn.fetch(
            "SELECT * FROM conversations WHERE user_id = $1 ORDER BY updated_at DESC",
            user_id,
        )
        return _rows_to_dicts(rows)


async def get_conversation(user_id: str, conversation_id: str) -> RowDict | None:
    async with get_db() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1 AND user_id = $2",
            conversation_id,
            user_id,
        )
        return _row_to_dict(row)


async def update_conversation(
    user_id: str,
    conversation_id: str,
    title: str | None = None,
    system_prompt: str | None = None,
    model_params: dict[str, object] | None = None,
) -> RowDict | None:
    set_fragments: list[str] = []
    params: list[object] = []
    next_idx = 1

    if title is not None:
        set_fragments.append(f"title = ${next_idx}")
        params.append(title)
        next_idx += 1
    if system_prompt is not None:
        set_fragments.append(f"system_prompt = ${next_idx}")
        params.append(system_prompt)
        next_idx += 1
    if model_params is not None:
        set_fragments.append(f"model_params = ${next_idx}")
        params.append(json.dumps(model_params))
        next_idx += 1

    if not set_fragments:
        return await get_conversation(user_id, conversation_id)

    set_fragments.append("updated_at = NOW()")
    user_idx = next_idx
    conv_idx = next_idx + 1
    params.extend([user_id, conversation_id])

    async with get_db() as conn:
        row = await conn.fetchrow(
            f"UPDATE conversations SET {', '.join(set_fragments)} "
            f"WHERE user_id = ${user_idx} AND id = ${conv_idx} RETURNING *",
            *params,
        )
        return _row_to_dict(row)


async def delete_conversation(user_id: str, conversation_id: str) -> bool:
    async with get_db() as conn:
        status = await conn.execute(
            "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
            conversation_id,
            user_id,
        )
        return _affected_row_count(status) > 0


async def add_message(
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    reasoning: str | None = None,
) -> RowDict:
    async with get_db() as conn:
        async with conn.transaction():
            owns = await conn.fetchval(
                "SELECT id FROM conversations WHERE user_id = $1 AND id = $2",
                user_id,
                conversation_id,
            )
            if owns is None:
                raise IntegrityViolation("Conversation not found")
            try:
                row = await conn.fetchrow(
                    "INSERT INTO messages (conversation_id, role, content, reasoning) "
                    "VALUES ($1, $2, $3, $4) RETURNING *",
                    conversation_id,
                    role,
                    content,
                    reasoning,
                )
            except asyncpg.exceptions.PostgresError as exc:
                raise _wrap_pg_error(exc) from exc
            _ = await conn.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
                conversation_id,
            )
        if row is None:
            raise RuntimeError("Failed to create message")
        return dict(row)


async def get_messages(user_id: str, conversation_id: str) -> list[RowDict]:
    async with get_db() as conn:
        rows = await conn.fetch(
            """
            SELECT messages.*
            FROM messages
            JOIN conversations ON conversations.id = messages.conversation_id
            WHERE conversations.user_id = $1 AND messages.conversation_id = $2
            ORDER BY messages.created_at ASC, messages.id ASC
            """,
            user_id,
            conversation_id,
        )
        return _rows_to_dicts(rows)


async def add_attachment(
    user_id: str,
    conversation_id: str,
    message_id: int | None,
    filename: str,
    file_hash: str,
    pages: int | None,
    markdown_content: str,
) -> RowDict:
    async with get_db() as conn:
        async with conn.transaction():
            owns = await conn.fetchval(
                "SELECT id FROM conversations WHERE user_id = $1 AND id = $2",
                user_id,
                conversation_id,
            )
            if owns is None:
                raise IntegrityViolation("Conversation not found")
            try:
                row = await conn.fetchrow(
                    "INSERT INTO attachments "
                    "(conversation_id, message_id, filename, file_hash, pages, markdown_content) "
                    "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
                    conversation_id,
                    message_id,
                    filename,
                    file_hash,
                    pages,
                    markdown_content,
                )
            except asyncpg.exceptions.PostgresError as exc:
                raise _wrap_pg_error(exc) from exc
            _ = await conn.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
                conversation_id,
            )
        if row is None:
            raise RuntimeError("Failed to create attachment")
        return dict(row)


async def list_conversation_attachments(
    user_id: str,
    conversation_id: str,
) -> list[RowDict]:
    async with get_db() as conn:
        rows = await conn.fetch(
            """
            SELECT attachments.*
            FROM attachments
            JOIN conversations ON conversations.id = attachments.conversation_id
            WHERE conversations.user_id = $1 AND attachments.conversation_id = $2
            ORDER BY attachments.created_at ASC, attachments.id ASC
            """,
            user_id,
            conversation_id,
        )
        return _rows_to_dicts(rows)


async def delete_attachment(user_id: str, attachment_id: int) -> bool:
    async with get_db() as conn:
        status = await conn.execute(
            """
            DELETE FROM attachments
            WHERE id = $1 AND conversation_id IN (
                SELECT id FROM conversations WHERE user_id = $2
            )
            """,
            attachment_id,
            user_id,
        )
        return _affected_row_count(status) > 0


async def add_image_attachment(
    user_id: str,
    conversation_id: str,
    filename: str,
    file_hash: str,
    mime_type: str,
    width: int,
    height: int,
    byte_size: int,
    file_path: str,
) -> RowDict:
    """Insert an image attachment row. message_id is NULL until linked at send time."""
    async with get_db() as conn:
        async with conn.transaction():
            owns = await conn.fetchval(
                "SELECT id FROM conversations WHERE user_id = $1 AND id = $2",
                user_id,
                conversation_id,
            )
            if owns is None:
                raise IntegrityViolation("Conversation not found")
            try:
                row = await conn.fetchrow(
                    "INSERT INTO attachments "
                    "(conversation_id, message_id, filename, file_hash, pages, "
                    " markdown_content, file_path, attachment_type, mime_type, "
                    " width, height, byte_size) "
                    "VALUES ($1, NULL, $2, $3, NULL, '', $4, 'image', $5, $6, $7, $8) "
                    "RETURNING *",
                    conversation_id,
                    filename,
                    file_hash,
                    file_path,
                    mime_type,
                    width,
                    height,
                    byte_size,
                )
            except asyncpg.exceptions.PostgresError as exc:
                raise _wrap_pg_error(exc) from exc
            _ = await conn.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
                conversation_id,
            )
        if row is None:
            raise RuntimeError("Failed to create image attachment")
        return dict(row)


async def update_attachment_message_id(
    user_id: str,
    attachment_ids: list[int],
    message_id: int,
) -> int:
    """Bind a list of attachments to a message after the message is INSERTed.

    Only attachments that belong to the caller (via conversation ownership) are
    updated. Returns the count of rows actually changed.
    """
    if not attachment_ids:
        return 0
    async with get_db() as conn:
        status = await conn.execute(
            """
            UPDATE attachments SET message_id = $1
            WHERE id = ANY($2::bigint[])
              AND conversation_id IN (
                  SELECT id FROM conversations WHERE user_id = $3
              )
            """,
            message_id,
            attachment_ids,
            user_id,
        )
        return _affected_row_count(status)


async def find_attachment_by_hash(
    user_id: str,
    file_hash: str,
    attachment_type: str = "image",
) -> RowDict | None:
    """Find the most recent attachment with this hash owned by the user."""
    async with get_db() as conn:
        row = await conn.fetchrow(
            """
            SELECT a.*
            FROM attachments a
            JOIN conversations c ON c.id = a.conversation_id
            WHERE c.user_id = $1 AND a.file_hash = $2 AND a.attachment_type = $3
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT 1
            """,
            user_id,
            file_hash,
            attachment_type,
        )
        return _row_to_dict(row)


async def get_attachment(user_id: str, attachment_id: int) -> RowDict | None:
    """Fetch one attachment row, scoped to the caller's conversations."""
    async with get_db() as conn:
        row = await conn.fetchrow(
            """
            SELECT a.*
            FROM attachments a
            JOIN conversations c ON c.id = a.conversation_id
            WHERE c.user_id = $1 AND a.id = $2
            """,
            user_id,
            attachment_id,
        )
        return _row_to_dict(row)


async def is_file_path_orphan(file_path: str) -> bool:
    """True when no attachment references this file_path anymore."""
    async with get_db() as conn:
        row = await conn.fetchval(
            "SELECT 1 FROM attachments WHERE file_path = $1 LIMIT 1",
            file_path,
        )
        return row is None


async def list_image_attachments_by_message(
    user_id: str,
    conversation_id: str,
) -> dict[int, list[RowDict]]:
    """All image attachments in this conversation, grouped by ``message_id``.

    Only includes attachments that have been linked to a message
    (``message_id IS NOT NULL``) so unlinked drafts do not appear in history.
    Authorization is enforced through the conversation join.
    """
    async with get_db() as conn:
        rows = await conn.fetch(
            """
            SELECT a.*
            FROM attachments a
            JOIN conversations c ON c.id = a.conversation_id
            WHERE c.user_id = $1
              AND a.conversation_id = $2
              AND a.attachment_type = 'image'
              AND a.message_id IS NOT NULL
            ORDER BY a.created_at ASC, a.id ASC
            """,
            user_id,
            conversation_id,
        )
    grouped: dict[int, list[RowDict]] = {}
    for raw in rows:
        row = dict(raw)
        message_id = row.get("message_id")
        if isinstance(message_id, int):
            grouped.setdefault(message_id, []).append(row)
    return grouped


async def find_orphan_image_paths(image_dir: str) -> set[str]:
    """File paths under ``image_dir`` that no attachment row references.

    Used by an offline sweep to clean files left behind when DELETE happened
    outside the helper that handles cleanup.
    """
    from pathlib import Path

    base = Path(image_dir)
    if not base.exists():
        return set()
    on_disk = {str(p) for p in base.iterdir() if p.is_file()}
    if not on_disk:
        return set()
    async with get_db() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT file_path FROM attachments "
            "WHERE attachment_type = 'image' AND file_path IS NOT NULL"
        )
    referenced = {str(Path(cast(str, r["file_path"]))) for r in rows}
    return {p for p in on_disk if p not in referenced}
