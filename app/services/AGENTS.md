<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# services

## Purpose
Stateless service layer between routers and the outside world: password/session/API-key cryptography, PostgreSQL CRUD via asyncpg, and the vLLM HTTP client.

## Key Files
| File | Description |
|------|-------------|
| `auth.py` | PBKDF2-SHA256 password hashing (600k iters), session token generation/SHA-256 hashing, API key generation/hashing, cookie helpers, `get_current_user` / `get_session_user_or_401` FastAPI dependencies |
| `database.py` | All PostgreSQL CRUD over `asyncpg`. Defines abstract `IntegrityViolation` / `NotFound` exceptions so routers stay driver-agnostic; private `_wrap_pg_error` translates asyncpg's unique/foreign-key/check/not-null errors. INSERTs use `RETURNING *` for single round-trip; multi-statement helpers (`add_message`, `add_attachment`, `add_image_attachment`) wrap in `async with conn.transaction():`. Covers users, sessions, api_keys (with retention-window purge), conversations, messages, attachments (PDF + image variants, dedup-by-hash, message linkage, orphan detection). |
| `llm.py` | `LLMService`: `list_models`, `create_chat_completion`, `stream_chat_completion`, `stream_chat_completion_proxy`, `check_health`. Streams SSE bytes from vLLM and emits `data: {"type":"error",...}` on failure |
| `pdf_parser.py` | HTTP client for the `pdf-parser` sidecar. Exposes `parse_pdf(client, file_bytes, filename)` (returns `{markdown, pages, duration_ms}`), `file_hash(bytes)`, and `PdfParserError`. Reuses `app.state.http_client` when passed |
| `image_store.py` | Pillow-based image attachment helper. `resize_and_save(bytes, dest_dir)` validates PNG/JPEG/WebP, resizes to ≤ `image_max_dimension`, re-encodes as JPEG (strips EXIF), sha256-dedups on disk. `load_image_b64(file_path)` returns `data:image/jpeg;base64,…` for vLLM `image_url` content blocks. `remove_image_file(file_path)` for orphan cleanup |
| `__init__.py` | Empty package marker |

## For AI Agents

### Working In This Directory
- **Never store raw API keys or session tokens.** The DB only ever sees SHA-256 hashes (`hash_session_token`, `hash_api_key`).
- Password hashing uses PBKDF2-SHA256 with 600,000 iterations and a 16-byte random salt. Both iterations and digest must stay in sync between `hash_password` and `verify_password`.
- Use `hmac.compare_digest` for hash comparisons (already wired in `verify_password`).
- `get_current_user` accepts both session cookies and bearer/`X-API-Key` headers; `get_session_user_or_401` is cookie-only and is what protects `/api/auth/api-keys` management routes.
- Revoked API keys remain in the table for `settings.api_key_revocation_retention_minutes` (default 5) and are purged on next read/write via `_purge_expired_revoked_api_keys`.
- `LLMService` accepts an optional `httpx.AsyncClient` — pass `app.state.http_client` from a request handler so streams reuse the lifespan-scoped client.

### Testing Requirements
- Mock `httpx.AsyncClient.stream` for `LLMService` tests — do not hit a live vLLM.
- DB tests run against the session-scoped testcontainers PG fixture in `tests/conftest.py`. Each test starts with all tables truncated, and `get_db()` is monkeypatched to a per-call connection so multiple `asyncio.run` calls in one test do not share an event loop with a long-lived pool.

### Common Patterns
- All DB helpers open a fresh connection through `get_db()`; multi-step operations group their statements inside a single `async with get_db() as db:` block.
- SSE error frames use `data: {"type":"error","message":"..."}\n\n` (see `_error_event`).
- vLLM responses are validated to be `text/event-stream` before streaming; otherwise raise `LLMServiceError`.

## Dependencies

### Internal
- `app.config.settings`, `app.database.get_db`.

### External
- `asyncpg`, `httpx`, `pillow` (`image_store`), stdlib `hashlib`/`hmac`/`secrets`/`uuid`.

<!-- MANUAL: -->
