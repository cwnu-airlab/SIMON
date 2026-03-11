"""CRUD operations for conversations and messages."""

import json
import uuid
from typing import cast

import aiosqlite

from app.config import settings
from app.database import get_db

RowDict = dict[str, object]


def _row_to_dict(row: aiosqlite.Row) -> RowDict:
    values = cast(tuple[object, ...], tuple(row))
    return {key: value for key, value in zip(row.keys(), values, strict=True)}


async def _purge_expired_revoked_api_keys(db: aiosqlite.Connection) -> None:
    retention_window = f"-{settings.api_key_revocation_retention_minutes} minutes"
    _ = await db.execute(
        "DELETE FROM api_keys WHERE revoked_at IS NOT NULL "
        + "AND datetime(revoked_at) <= datetime('now', ?)",
        (retention_window,),
    )


async def create_user(
    username: str,
    password_hash: str,
    password_salt: str,
) -> RowDict:
    user_id = uuid.uuid4().hex
    async with get_db() as db:
        _ = await db.execute(
            "INSERT INTO users (id, username, password_hash, password_salt) VALUES (?, ?, ?, ?)",
            (user_id, username, password_hash, password_salt),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to create user")
        return _row_to_dict(row)


async def get_user_by_username(username: str) -> RowDict | None:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def create_session(session_id: str, user_id: str, expires_at: str) -> None:
    async with get_db() as db:
        _ = await db.execute(
            "INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)",
            (session_id, user_id, expires_at),
        )
        await db.commit()


async def create_api_key(user_id: str, name: str, key_hash: str, key_prefix: str) -> RowDict:
    api_key_id = uuid.uuid4().hex
    async with get_db() as db:
        await _purge_expired_revoked_api_keys(db)
        _ = await db.execute(
            "INSERT INTO api_keys (id, user_id, name, key_hash, key_prefix) VALUES (?, ?, ?, ?, ?)",
            (api_key_id, user_id, name, key_hash, key_prefix),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM api_keys WHERE id = ? AND user_id = ?",
            (api_key_id, user_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to create API key")
        return _row_to_dict(row)


async def list_api_keys(user_id: str) -> list[RowDict]:
    async with get_db() as db:
        await _purge_expired_revoked_api_keys(db)
        cursor = await db.execute(
            "SELECT * FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows]


async def revoke_api_key(user_id: str, api_key_id: str) -> bool:
    async with get_db() as db:
        await _purge_expired_revoked_api_keys(db)
        cursor = await db.execute(
            "UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP "
            + "WHERE user_id = ? AND id = ? AND revoked_at IS NULL",
            (user_id, api_key_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_api_key_user(key_hash: str) -> RowDict | None:
    async with get_db() as db:
        await _purge_expired_revoked_api_keys(db)
        cursor = await db.execute(
            """
            SELECT api_keys.id AS api_key_id, users.id, users.username, users.created_at
            FROM api_keys
            JOIN users ON users.id = api_keys.user_id
            WHERE api_keys.key_hash = ? AND api_keys.revoked_at IS NULL
            """,
            (key_hash,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        _ = await db.execute(
            "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_hash = ?",
            (key_hash,),
        )
        await db.commit()
        return _row_to_dict(row)


async def get_session_user(session_id: str) -> RowDict | None:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT sessions.user_id, sessions.expires_at, users.username, users.created_at
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.id = ?
            """,
            (session_id,),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def delete_session(session_id: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()
        return cursor.rowcount > 0


async def create_conversation(user_id: str) -> RowDict:
    conv_id = uuid.uuid4().hex
    async with get_db() as db:
        _ = await db.execute(
            "INSERT INTO conversations (id, user_id) VALUES (?, ?)",
            (conv_id, user_id),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to create conversation")
        return _row_to_dict(row)


async def list_conversations(user_id: str) -> list[RowDict]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows]


async def get_conversation(user_id: str, conversation_id: str) -> RowDict | None:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def update_conversation(
    user_id: str,
    conversation_id: str,
    title: str | None = None,
    system_prompt: str | None = None,
    model_params: dict[str, object] | None = None,
) -> RowDict | None:
    updates: list[str] = []
    params: list[str] = []

    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if system_prompt is not None:
        updates.append("system_prompt = ?")
        params.append(system_prompt)
    if model_params is not None:
        updates.append("model_params = ?")
        params.append(json.dumps(model_params))

    if not updates:
        return await get_conversation(user_id, conversation_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(user_id)
    params.append(conversation_id)

    async with get_db() as db:
        _ = await db.execute(
            f"UPDATE conversations SET {', '.join(updates)} WHERE user_id = ? AND id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE user_id = ? AND id = ?",
            (user_id, conversation_id),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def delete_conversation(user_id: str, conversation_id: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM conversations WHERE user_id = ? AND id = ?",
            (user_id, conversation_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def add_message(
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    reasoning: str | None = None,
) -> RowDict:
    async with get_db() as db:
        conversation_cursor = await db.execute(
            "SELECT id FROM conversations WHERE user_id = ? AND id = ?",
            (user_id, conversation_id),
        )
        conversation = await conversation_cursor.fetchone()
        if conversation is None:
            raise aiosqlite.IntegrityError("Conversation not found")
        cursor = await db.execute(
            "INSERT INTO messages (conversation_id, role, content, reasoning) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, reasoning),
        )
        _ = await db.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,),
        )
        await db.commit()
        msg_cursor = await db.execute("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,))
        row = await msg_cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to create message")
        return _row_to_dict(row)


async def get_messages(user_id: str, conversation_id: str) -> list[RowDict]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT messages.*
            FROM messages
            JOIN conversations ON conversations.id = messages.conversation_id
            WHERE conversations.user_id = ? AND messages.conversation_id = ?
            ORDER BY messages.created_at ASC
            """,
            (user_id, conversation_id),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows]
