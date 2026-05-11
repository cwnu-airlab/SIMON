"""Tests for the VLM image attachment feature.

PostgreSQL is provided by the session-scoped ``pg_dsn`` fixture in
``conftest.py``; per-test isolation (TRUNCATE + ``get_db`` per-call connection
override) is wired up by the autouse ``_pg_isolation`` fixture.

Covers:
- Image upload via the attachments router (PNG/JPEG/WEBP accepted, GIF rejected,
  oversize rejected).
- Pillow resize and sha256 dedup.
- ``_build_llm_messages`` content-array reconstruction for user turns with
  image attachments, plus PDF + image coexistence regression.
- Backward compatibility: messages without image attachments keep ``content``
  as a string (byte-identical to pre-VLM behavior).
"""

from __future__ import annotations

import asyncio
import io
import os
import secrets
import tempfile
import unittest
from pathlib import Path

from PIL import Image


def _per_test_images_dir() -> str:
    images_dir = tempfile.mkdtemp(prefix="simon-vlm-images-")
    return images_dir


def _build_test_app(images_dir: str):
    """Return the FastAPI app with ``settings.images_dir`` pointed at a tmp dir."""
    from app.config import settings
    from app.main import app as fastapi_app

    settings.images_dir = images_dir
    return fastapi_app


def _make_jpeg(width: int, height: int, color: str | tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buf, format="JPEG")
    return buf.getvalue()


class ImageUploadRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        self.images_dir = _per_test_images_dir()
        self.app = _build_test_app(self.images_dir)
        self.client = TestClient(self.app)

    def _create_authed_user(self, username: str) -> tuple[dict[str, object], str]:
        from app.services.auth import build_session_expiry, hash_session_token
        from app.services.database import create_session, create_user

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

    def test_upload_image_jpeg(self) -> None:
        user, token = self._create_authed_user("alice")
        conv_id = self._create_conversation(str(user["id"]))
        self.client.cookies.set("simon_session", token)

        resp = self.client.post(
            f"/api/conversations/{conv_id}/attachments",
            files={"file": ("cat.jpg", _make_jpeg(100, 100, "red"), "image/jpeg")},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        body = resp.json()
        self.assertEqual(body["attachment_type"], "image")
        self.assertEqual(body["mime_type"], "image/jpeg")
        self.assertEqual(body["filename"], "cat.jpg")
        self.assertEqual(body["width"], 100)
        self.assertEqual(body["height"], 100)

    def test_upload_unsupported_format(self) -> None:
        user, token = self._create_authed_user("alice")
        conv_id = self._create_conversation(str(user["id"]))
        self.client.cookies.set("simon_session", token)

        gif_buf = io.BytesIO()
        Image.new("RGB", (40, 40)).save(gif_buf, format="GIF")
        resp = self.client.post(
            f"/api/conversations/{conv_id}/attachments",
            files={"file": ("a.gif", gif_buf.getvalue(), "image/gif")},
        )
        self.assertEqual(resp.status_code, 415)

    def test_upload_oversize(self) -> None:
        user, token = self._create_authed_user("alice")
        conv_id = self._create_conversation(str(user["id"]))
        self.client.cookies.set("simon_session", token)

        big = b"\xff\xd8\xff\xe0" + b"X" * (11 * 1024 * 1024)
        resp = self.client.post(
            f"/api/conversations/{conv_id}/attachments",
            files={"file": ("big.jpg", big, "image/jpeg")},
        )
        self.assertEqual(resp.status_code, 413)

    def test_resize_max_dimension(self) -> None:
        user, token = self._create_authed_user("alice")
        conv_id = self._create_conversation(str(user["id"]))
        self.client.cookies.set("simon_session", token)

        resp = self.client.post(
            f"/api/conversations/{conv_id}/attachments",
            files={"file": ("huge.png", _make_jpeg(5000, 3000, "blue"), "image/jpeg")},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        body = resp.json()
        self.assertLessEqual(max(body["width"], body["height"]), 1568)

    def test_dedup_by_hash(self) -> None:
        from app.services.database import list_conversation_attachments

        user, token = self._create_authed_user("alice")
        conv_id = self._create_conversation(str(user["id"]))
        self.client.cookies.set("simon_session", token)

        same = _make_jpeg(80, 80, (10, 200, 50))
        r1 = self.client.post(
            f"/api/conversations/{conv_id}/attachments",
            files={"file": ("a.jpg", same, "image/jpeg")},
        )
        r2 = self.client.post(
            f"/api/conversations/{conv_id}/attachments",
            files={"file": ("b.jpg", same, "image/jpeg")},
        )
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)

        rows = asyncio.run(
            list_conversation_attachments(str(user["id"]), conv_id)
        )
        image_rows = [r for r in rows if r.get("attachment_type") == "image"]
        self.assertEqual(len(image_rows), 2)
        paths = {r["file_path"] for r in image_rows}
        self.assertEqual(len(paths), 1)
        only_path = next(iter(paths))
        self.assertTrue(Path(str(only_path)).exists())


class BuildLlmMessagesImageTests(unittest.TestCase):
    """Pure-function checks on _build_llm_messages multimodal behaviour."""

    def setUp(self) -> None:
        self.images_dir = _per_test_images_dir()
        _build_test_app(self.images_dir)
        os.makedirs(self.images_dir, exist_ok=True)
        self.image_path = os.path.join(self.images_dir, "test.jpg")
        Path(self.image_path).write_bytes(_make_jpeg(32, 32, "purple"))

    def test_build_llm_messages_no_image_keeps_string(self) -> None:
        from app.routers.chat import _build_llm_messages

        msgs = _build_llm_messages(
            "system",
            [],
            [
                {"role": "user", "content": "Q1"},
                {"role": "assistant", "content": "A1"},
            ],
        )
        self.assertEqual(
            msgs,
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "Q1"},
                {"role": "assistant", "content": "A1"},
            ],
        )

    def test_build_llm_messages_image_user_turn_becomes_array(self) -> None:
        from app.routers.chat import _build_llm_messages

        history = [
            {
                "role": "user",
                "content": "describe",
                "image_attachments": [
                    {"file_path": self.image_path, "mime_type": "image/jpeg"}
                ],
            },
        ]
        msgs = _build_llm_messages("", [], history)
        self.assertEqual(len(msgs), 1)
        content = msgs[0]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[0]["text"], "describe")
        self.assertEqual(content[1]["type"], "image_url")
        self.assertTrue(
            content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        )

    def test_image_pdf_coexist(self) -> None:
        from app.routers.chat import _build_llm_messages

        pdf_atts = [
            {
                "attachment_type": "pdf",
                "filename": "doc.pdf",
                "pages": 5,
                "markdown_content": "# pdf body",
            }
        ]
        history = [
            {
                "role": "user",
                "content": "image+text",
                "image_attachments": [
                    {"file_path": self.image_path, "mime_type": "image/jpeg"}
                ],
            }
        ]
        msgs = _build_llm_messages("", pdf_atts, history)
        self.assertEqual([m["role"] for m in msgs], ["system", "user"])
        self.assertIn("doc.pdf", msgs[0]["content"])
        self.assertIsInstance(msgs[1]["content"], list)

    def test_missing_image_file_skipped_gracefully(self) -> None:
        from app.routers.chat import _build_llm_messages

        history = [
            {
                "role": "user",
                "content": "q",
                "image_attachments": [
                    {"file_path": "/no/such/file.jpg", "mime_type": "image/jpeg"}
                ],
            }
        ]
        msgs = _build_llm_messages("", [], history)
        self.assertEqual(msgs[0]["content"], [{"type": "text", "text": "q"}])


if __name__ == "__main__":
    unittest.main()
