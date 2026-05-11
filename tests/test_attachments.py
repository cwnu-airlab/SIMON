"""Smoke tests for the PDF attachment feature.

These tests intentionally mock the pdf-parser sidecar so the suite can run
without Java / Docker. PostgreSQL is provided by the session-scoped
``pg_dsn`` fixture in ``conftest.py``; per-test isolation (TRUNCATE +
``get_db`` per-call connection override) is wired up by the autouse
``_pg_isolation`` fixture.
"""

from __future__ import annotations

import asyncio
import secrets
import unittest
from collections.abc import Callable
from typing import cast


class AttachmentsRouterTests(unittest.TestCase):
    """End-to-end smoke for /api/conversations/{id}/attachments/*."""

    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app
        from app.routers import attachments as attachments_module
        from app.services import pdf_parser as pdf_parser_module

        self.app = app

        async def fake_parse(
            client, file_bytes, filename, *, force_ocr=False
        ) -> dict[str, object]:
            return {
                "markdown": f"# Mock content for {filename}\nbytes={len(file_bytes)}",
                "pages": 7,
                "duration_ms": 5,
            }

        # Patch on both modules so refs stay current regardless of import order.
        pdf_parser_module.parse_pdf = cast(Callable[..., object], fake_parse)
        attachments_module.parse_pdf = cast(Callable[..., object], fake_parse)
        self.client = TestClient(self.app)

    def _create_authed_user(self, username: str) -> tuple[dict[str, object], str]:
        from app.services.auth import build_session_expiry, hash_session_token
        from app.services.database import (
            create_session,
            create_user,
        )

        async def setup():
            user = await create_user(username, "h", "s")
            token = secrets.token_urlsafe(32)
            await create_session(
                hash_session_token(token),
                str(user["id"]),
                build_session_expiry(),
            )
            return user, token

        return asyncio.run(setup())

    def _create_conversation(self, user_id: str) -> str:
        from app.services.database import create_conversation

        return str(asyncio.run(create_conversation(user_id))["id"])

    def test_upload_requires_auth(self) -> None:
        user, _token = self._create_authed_user("alice")
        conv_id = self._create_conversation(str(user["id"]))

        anon = self.client.__class__(self.app)
        resp = anon.post(
            f"/api/conversations/{conv_id}/attachments",
            files={"file": ("a.pdf", b"%PDF-1.4 hi", "application/pdf")},
        )
        self.assertEqual(resp.status_code, 401)

    def test_upload_authed_returns_meta(self) -> None:
        user, token = self._create_authed_user("alice")
        conv_id = self._create_conversation(str(user["id"]))

        self.client.cookies.set("simon_session", token)
        resp = self.client.post(
            f"/api/conversations/{conv_id}/attachments",
            files={"file": ("hello.pdf", b"%PDF-1.4 hi", "application/pdf")},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        body = resp.json()
        self.assertEqual(body["filename"], "hello.pdf")
        self.assertEqual(body["pages"], 7)
        self.assertNotIn("markdown_content", body)

    def test_other_users_conversation_404(self) -> None:
        owner, _ = self._create_authed_user("alice")
        conv_id = self._create_conversation(str(owner["id"]))

        _other, token = self._create_authed_user("bob")
        self.client.cookies.set("simon_session", token)

        upload = self.client.post(
            f"/api/conversations/{conv_id}/attachments",
            files={"file": ("a.pdf", b"%PDF-1.4 hi", "application/pdf")},
        )
        self.assertEqual(upload.status_code, 404)
        listing = self.client.get(f"/api/conversations/{conv_id}/attachments")
        self.assertEqual(listing.status_code, 404)


class BuildLlmMessagesTests(unittest.TestCase):
    """Pure function-level checks on attachment system-message injection."""

    def test_no_attachments_keeps_legacy_shape(self) -> None:
        from app.routers.chat import _build_llm_messages

        msgs = _build_llm_messages(
            "You are helpful.",
            [],
            [
                {"role": "user", "content": "q1"},
                {"role": "assistant", "content": "a1"},
            ],
        )
        self.assertEqual(
            msgs,
            [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "q1"},
                {"role": "assistant", "content": "a1"},
            ],
        )

    def test_attachment_injected_as_single_system_block(self) -> None:
        from app.routers.chat import _build_llm_messages

        msgs = _build_llm_messages(
            "You are helpful.",
            [{"filename": "a.pdf", "pages": 3, "markdown_content": "# title\nbody"}],
            [{"role": "user", "content": "q1"}],
        )
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[0], {"role": "system", "content": "You are helpful."})
        self.assertEqual(msgs[1]["role"], "system")
        self.assertIn("a.pdf", msgs[1]["content"])
        self.assertIn("# title", msgs[1]["content"])
        self.assertEqual(msgs[2]["role"], "user")

    def test_format_attachments_block_empty(self) -> None:
        from app.routers.chat import _format_attachments_block

        self.assertEqual(_format_attachments_block([]), "")

    def test_truncate_cap(self) -> None:
        import app.config
        from app.routers.chat import _format_attachments_block

        original_cap = app.config.settings.pdf_max_markdown_chars
        try:
            app.config.settings.pdf_max_markdown_chars = 100
            block = _format_attachments_block(
                [{"filename": "big.pdf", "pages": 99, "markdown_content": "X" * 5000}]
            )
            self.assertIn("[truncated, capped at 100 chars]", block)
        finally:
            app.config.settings.pdf_max_markdown_chars = original_cap


if __name__ == "__main__":
    unittest.main()
