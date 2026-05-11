"""PostgreSQL integration tests for app/services/database.py.

Covers behaviors that only make sense against a real PG (CITEXT
case-insensitive UNIQUE, ``RETURNING`` populated rows, cascade vs SET NULL,
and IDENTITY-based auto increment).
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime, timedelta

from app.services.database import (
    IntegrityViolation,
    add_attachment,
    add_image_attachment,
    add_message,
    create_conversation,
    create_session,
    create_user,
    delete_conversation,
    get_session_user,
    get_user_by_username,
    update_attachment_message_id,
)


def _run(coro):
    return asyncio.run(coro)


class CitextUsernameTests(unittest.TestCase):
    def test_citext_unique_case_insensitive(self) -> None:
        async def scenario():
            await create_user("Alice", "h", "s")
            with self.assertRaises(IntegrityViolation):
                await create_user("alice", "h", "s")
            with self.assertRaises(IntegrityViolation):
                await create_user("ALICE", "h", "s")

        _run(scenario())

    def test_lookup_is_case_insensitive(self) -> None:
        async def scenario():
            user = await create_user("Bob", "h", "s")
            for variant in ("bob", "BOB", "Bob"):
                row = await get_user_by_username(variant)
                self.assertIsNotNone(row)
                self.assertEqual(row["id"], user["id"])

        _run(scenario())


class ReturningIdTests(unittest.TestCase):
    def test_add_message_returns_id_via_returning(self) -> None:
        async def scenario():
            user = await create_user("alice", "h", "s")
            conv = await create_conversation(user["id"])
            m1 = await add_message(user["id"], conv["id"], "user", "first")
            m2 = await add_message(user["id"], conv["id"], "user", "second")
            self.assertIsInstance(m1["id"], int)
            self.assertGreater(m1["id"], 0)
            self.assertNotEqual(m1["id"], m2["id"])

        _run(scenario())

    def test_add_attachment_returns_full_row(self) -> None:
        async def scenario():
            user = await create_user("alice", "h", "s")
            conv = await create_conversation(user["id"])
            row = await add_attachment(
                user["id"], conv["id"], None, "doc.pdf", "h", 5, "# pdf"
            )
            self.assertIsInstance(row["id"], int)
            self.assertEqual(row["filename"], "doc.pdf")
            self.assertEqual(row["attachment_type"], "pdf")

        _run(scenario())


class CascadeAndSetNullTests(unittest.TestCase):
    def test_conversation_delete_cascades_messages_and_attachments(self) -> None:
        async def scenario():
            import asyncpg

            from app.database import get_db

            user = await create_user("alice", "h", "s")
            conv = await create_conversation(user["id"])
            await add_message(user["id"], conv["id"], "user", "x")
            await add_attachment(
                user["id"], conv["id"], None, "p.pdf", "h", 1, "#"
            )
            await delete_conversation(user["id"], conv["id"])
            async with get_db() as conn:
                msg_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM messages WHERE conversation_id = $1", conv["id"]
                )
                att_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM attachments WHERE conversation_id = $1", conv["id"]
                )
            self.assertEqual(msg_count, 0)
            self.assertEqual(att_count, 0)
            _ = asyncpg  # keep import for clarity

        _run(scenario())

    def test_message_delete_sets_attachment_message_id_null(self) -> None:
        async def scenario():
            from app.database import get_db

            user = await create_user("alice", "h", "s")
            conv = await create_conversation(user["id"])
            msg = await add_message(user["id"], conv["id"], "user", "ask")
            att = await add_image_attachment(
                user["id"],
                conv["id"],
                "cat.jpg",
                "h-cat",
                "image/jpeg",
                100,
                100,
                500,
                "data/images/h-cat.jpg",
            )
            await update_attachment_message_id(user["id"], [att["id"]], msg["id"])

            async with get_db() as conn:
                await conn.execute("DELETE FROM messages WHERE id = $1", msg["id"])
                mid = await conn.fetchval(
                    "SELECT message_id FROM attachments WHERE id = $1", att["id"]
                )
            self.assertIsNone(mid)

        _run(scenario())


class SessionTimezoneTests(unittest.TestCase):
    def test_create_session_accepts_aware_datetime(self) -> None:
        async def scenario():
            user = await create_user("alice", "h", "s")
            expires = datetime.now(UTC) + timedelta(hours=1)
            await create_session("sess-1", user["id"], expires)
            row = await get_session_user("sess-1")
            self.assertIsNotNone(row)
            self.assertEqual(row["expires_at"], expires)

        _run(scenario())


if __name__ == "__main__":
    unittest.main()
