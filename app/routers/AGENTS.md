<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# routers

## Purpose
FastAPI routers that expose two API surfaces:
- `/api/*` — app-native endpoints used by the SvelteKit frontend (custom SSE event shape).
- `/v1/*` — OpenAI-compatible passthrough used by external tools and agent clients.

## Key Files
| File | Description |
|------|-------------|
| `auth.py` | `/api/auth/*` — signup, login, logout, `/me`, API key list/create/revoke |
| `chat.py` | `POST /api/chat/completions` — auto-creates conversation if missing, persists user + assistant messages, proxies the SSE stream and adds a `{"type":"start","conversation_id":...}` prelude |
| `conversations.py` | `/api/conversations` CRUD — list, create, get-with-messages, patch (title / system_prompt / model_params), delete |
| `openai.py` | `/v1/models` and `/v1/chat/completions` — thin proxy to vLLM, supports both JSON and streaming responses; auth via `get_current_user` (cookie or API key) |
| `attachments.py` | `POST /api/conversations/{id}/attachments` (multipart upload, branches on content-type: PDF → pdf-parser sidecar, image → Pillow `image_store`), `GET /api/conversations/{id}/attachments` (list, no markdown body), `GET /api/conversations/{id}/attachments/{att_id}/raw` (auth-scoped image bytes for browser display), `DELETE /api/conversations/{id}/attachments/{att_id}` (orphan-aware: unlinks disk file when last reference goes) |
| `__init__.py` | Empty package marker |

## For AI Agents

### Working In This Directory
- Routers must always declare `prefix="/api/..."` or `prefix="/v1"` in `APIRouter(...)` and be registered in `app/main.py`.
- For protected endpoints choose the right dependency:
  - User-facing actions allowing API keys: `Depends(get_current_user)`.
  - Account management (logout, API key list/create/revoke): `Depends(get_session_user_or_401)` so external tools cannot manage credentials.
- Conversation routes scope every query by `user_id` — never trust a `conversation_id` without checking ownership.
- The SSE response in `chat.py` accumulates `content` and `reasoning` deltas itself; `_extract_stream_deltas` understands both `delta.reasoning` and `delta.reasoning_content` (different vLLM versions).
- `openai.py` uses `_shared_http_client(request)` to reuse the lifespan client; preserve this so streaming connections don't leak.
- Always set the streaming response headers `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no` to keep nginx from buffering.

### Testing Requirements
- Use FastAPI `TestClient` (or `httpx.AsyncClient` with `ASGITransport`) for endpoint tests.
- Stream tests should assert both the `data: {"type":"start"...}` prelude and the terminal `[DONE]`.

### Common Patterns
- Endpoint signature: `async def handler(body: PydanticModel, current_user: CurrentUser) -> ResponseModel:`.
- Convert SQLite row dicts to Pydantic responses with private `_to_*_response` helpers.
- Raise `HTTPException(status_code=...)` with descriptive `detail` for 4xx errors.

## Dependencies

### Internal
- `app.models.*` for schemas, `app.services.auth` for dependencies, `app.services.database` for CRUD, `app.services.llm` for the vLLM client.

### External
- `fastapi`, `httpx`, `aiosqlite` (only `IntegrityError` import).

<!-- MANUAL: -->
