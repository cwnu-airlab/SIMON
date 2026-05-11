# SIMON

SIMON is a self-hosted chat service built on top of FastAPI, SvelteKit, PostgreSQL, and vLLM.

It provides two access layers:

- a web UI for human users, with account-based chat history
- an OpenAI-compatible API surface for external tools and agent clients

The public deployment for this instance is available at:

- Web UI: `https://air.changwon.ac.kr/simon/`
- OpenAI-compatible API base: `https://air.changwon.ac.kr/simon/v1`

## Features

- local account signup and login
- per-user conversations and message history
- per-user API key creation and revocation
- revoked API keys are hard-deleted after 5 minutes
- app-specific REST and streaming chat API under `/api`
- OpenAI-compatible endpoints under `/v1`
- PDF attachments per conversation (extracted via OpenDataLoader sidecar, injected as a system message)
- Docker Compose deployment with backend, frontend, nginx, and pdf-parser

## Stack

- Backend: FastAPI, httpx, asyncpg, pydantic-settings, Pillow
- Frontend: SvelteKit 2, Svelte 5, Tailwind CSS 4
- Model backend: vLLM (Qwen3.5-9B multimodal)
- Database: PostgreSQL 16 (managed as a `postgres:16-alpine` Compose service; CITEXT username, BIGINT IDENTITY ids, TIMESTAMPTZ timestamps)
- PDF parsing: opendataloader-pdf sidecar (`pdf-parser/`)
- Runtime: Docker Compose

## Repository Layout

- `app/` - FastAPI backend
- `frontend/` - SvelteKit frontend
- `pdf-parser/` - PDF extraction sidecar (Java + opendataloader-pdf + FastAPI wrapper)
- `nginx/default.conf` - internal nginx routing for Compose deployment
- `docker-compose.yml` - production-style multi-container deployment
- `Dockerfile` - backend image
- `frontend/Dockerfile` - frontend image
- `tutorial.md` - OpenCode setup guide for first-time users
- `tutorial.ko.md` - Korean OpenCode setup guide

## Image Attachments (VLM)

The same chat input also accepts PNG / JPEG / WebP images (max 10MB) and SIMON forwards them to vLLM as proper OpenAI-compatible `image_url` content blocks so the model can describe / answer about the image.

- Backend Pillow resizes the upload to fit `IMAGE_MAX_DIMENSION` (default 1568 × 1568), re-encodes as JPEG (drops EXIF), sha256-deduplicates on disk, and stores under `simon-data:/app/data/images/<hash>.jpg`.
- Each image is **message-scoped**: it lives inside the user message it was attached to. History naturally preserves it, so the model can refer back across turns.
- The OpenAI-compatible `/v1/chat/completions` external API forwards multimodal payloads as-is to vLLM — image-capable clients (e.g. `image_url` with data URIs) work without backend changes.
- Requires the underlying vLLM model (`Qwen/Qwen3.5-9B`) to be served **without** `--language-model-only`, so the vision tower is loaded.

Settings (env / `.env`): `IMAGES_DIR` (default `data/images`), `IMAGE_MAX_DIMENSION` (default `1568`), `IMAGE_MAX_BYTES` (default `10485760`).

## PDF Attachments

Users can attach PDFs to a conversation. The flow:

1. Browser uploads via `POST /api/conversations/{id}/attachments` (multipart, max 50MB / 100 pages by default).
2. Backend forwards the file to the `pdf-parser` sidecar (`opendataloader-pdf` running on a JRE), which returns extracted markdown.
3. Markdown is stored once in the `attachments` table (`conversation_id` scope, `ON DELETE CASCADE` from the conversation).
4. Every subsequent chat turn re-injects the attachments as a single `system` message before the chat history, so the model has the full document context without duplicating it across turns. Total markdown is capped by `PDF_MAX_MARKDOWN_CHARS` (default 80000) and overflow is marked `[truncated, capped at <N> chars]`.

Relevant settings (env / `.env`):

- `PDF_PARSER_URL` (default `http://pdf-parser:8080`)
- `PDF_MAX_MARKDOWN_CHARS` (default `80000`)
- `PDF_MAX_FILE_MB` (default `50`)
- `PDF_MAX_PAGES` (default `100`)
- `PDF_OCR_LANG` (default `ko,en`)

See `pdf-parser/README.md` for the sidecar's API and operational notes (JVM cold start, OCR engine, model cache volume).

## Tutorials

- English: `tutorial.md`
- Korean: `tutorial.ko.md`

## Architecture

At runtime the stack looks like this:

1. outer reverse proxy (for this deployment, Apache) forwards `/simon/` to port `3080`
2. the Docker Compose `nginx` container listens on `3080`
3. internal nginx routes:
   - `/api/` -> FastAPI backend
   - `/v1/` -> FastAPI backend
   - everything else -> SvelteKit frontend
4. FastAPI calls the configured vLLM server

The backend stores:

- users
- browser sessions
- API keys
- conversations
- messages

## Configuration

Settings are loaded from `.env`.

Example:

```env
VLLM_BASE_URL=http://nginx:8081
VLLM_MODEL=Qwen/Qwen3.5-9B
POSTGRES_USER=simon
POSTGRES_PASSWORD=change_me
POSTGRES_DB=simon
DATABASE_URL=postgresql://simon:change_me@postgres:5432/simon
SESSION_COOKIE_SECURE=true
ORIGIN=https://air.changwon.ac.kr
```

Important settings:

- `VLLM_BASE_URL` - upstream vLLM server (defaults to the inner nginx LB at `http://nginx:8081` which round-robins across `vllm0`/`vllm1`)
- `VLLM_MODEL` - default model exposed by the service
- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` - PostgreSQL credentials consumed by both the `postgres` Compose service and the backend's DSN template
- `DATABASE_URL` - PostgreSQL DSN (`postgresql://user:pass@host:port/db`) read by `asyncpg.create_pool` at backend startup
- `SESSION_COOKIE_SECURE` - set `true` behind HTTPS
- `ORIGIN` - frontend origin used by the production frontend container

Backend defaults also include:

- session cookie name: `simon_session`
- session max age: 168 hours
- revoked API key retention window: 5 minutes

## Local Development

Requirements:

- Python 3.13+
- Node.js 22+
- a running vLLM server

### Backend

```bash
uv sync
uv run python -m app.main
```

The backend listens on `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs on Vite/SvelteKit and talks to the backend through its local dev setup.

### Checks

```bash
uv run ruff check app
cd frontend && npm run check
cd frontend && npm run build
```

## Docker Deployment

From the repository root:

```bash
docker compose up -d --build
```

This starts:

- `backend` on internal port `8000`
- `frontend` on internal port `3000`
- `nginx` on host port `3080`

To inspect service status:

```bash
docker compose ps
docker compose logs -f nginx backend frontend
```

To restart nginx after editing `nginx/default.conf`:

```bash
docker compose restart nginx
```

## Deploying Under `/simon`

This project supports a subpath deployment such as `https://example.com/simon/`.

The expected outer reverse proxy behavior is:

- redirect `/simon` -> `/simon/`
- strip the `/simon/` prefix before forwarding to the inner service on port `3080`

In that setup:

- browser app URLs become `/simon/...`
- inner nginx receives `/...`
- app API calls are routed through `/api/...`
- OpenAI-compatible calls are routed through `/v1/...`

If `/simon/api/...` works but `/simon/v1/...` returns the frontend 404 page, check that the inner nginx config includes both `/api/` and `/v1/` backend proxy locations.

## Authentication Model

SIMON supports two authentication methods.

### Browser Session

- users sign up or log in via the web UI
- the backend issues an `httpOnly` session cookie
- conversations are scoped to the logged-in user

### API Key

- API keys are created per user from the web UI
- the full key is shown only once at creation time
- the backend stores only a hash, not the raw key
- revoked keys stop working immediately
- revoked keys are fully deleted after 5 minutes

## User-Facing Web App

Public URL:

- `https://air.changwon.ac.kr/simon/`

Typical flow:

1. sign up or log in
2. create and manage conversations
3. open the API key modal from the sidebar if you want external access
4. create an API key for scripts, tools, or agents

## App API

The app-native API lives under `/api`.

Examples:

- `GET /api/health`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/auth/api-keys`
- `POST /api/auth/api-keys`
- `DELETE /api/auth/api-keys/{api_key_id}`
- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/{conversation_id}`
- `PATCH /api/conversations/{conversation_id}`
- `DELETE /api/conversations/{conversation_id}`
- `POST /api/conversations/{conversation_id}/attachments`
- `GET /api/conversations/{conversation_id}/attachments`
- `GET /api/conversations/{conversation_id}/attachments/{attachment_id}/raw`
- `DELETE /api/conversations/{conversation_id}/attachments/{attachment_id}`
- `POST /api/chat/completions`

The app chat endpoint is intended for the web UI and uses the service's custom SSE event shape.

## Uploading Attachments via API

The same `POST /api/conversations/{id}/attachments` endpoint accepts both PDFs and images — the backend dispatches on `Content-Type`. Both routes accept either `Authorization: Bearer <KEY>` or `X-API-Key: <KEY>` (or a session cookie from the web UI).

Limits (defaults, configurable via env):

- PDF: `application/pdf`, max 50MB, ≤ 100 pages
- Image: `image/png` / `image/jpeg` / `image/webp`, max 10MB, resized to fit 1568×1568 and re-encoded as JPEG (EXIF stripped)

PDFs are **conversation-scoped**: extracted markdown is stored once and re-injected as a system message every turn. Images are **message-scoped**: bind the returned `id` to a user message via `attachment_ids` so the model receives it in that turn (and on every replay of history).

### 1. Create a conversation (or reuse one)

```bash
CONV=$(curl -s -X POST "https://air.changwon.ac.kr/simon/api/conversations" \
  -H "Authorization: Bearer $API_KEY" | jq -r .id)
```

### 2a. Upload a PDF

```bash
curl -X POST "https://air.changwon.ac.kr/simon/api/conversations/$CONV/attachments" \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@report.pdf;type=application/pdf"
```

Response:

```json
{
  "id": 12,
  "filename": "report.pdf",
  "pages": 17,
  "attachment_type": "pdf",
  "mime_type": null,
  "created_at": "2026-05-09T10:11:12+00:00"
}
```

PDFs do **not** need to be passed in `attachment_ids` — once uploaded, every subsequent `POST /api/chat/completions` on the same conversation will automatically include the extracted markdown.

### 2b. Upload an image

```bash
ATT=$(curl -s -X POST "https://air.changwon.ac.kr/simon/api/conversations/$CONV/attachments" \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@photo.jpg;type=image/jpeg" | jq -r .id)
```

Response:

```json
{
  "id": 42,
  "filename": "photo.jpg",
  "attachment_type": "image",
  "mime_type": "image/jpeg",
  "width": 1280,
  "height": 853,
  "created_at": "2026-05-09T10:11:12+00:00"
}
```

### 3. Send a chat message that uses the image

Pass the attachment id(s) in `attachment_ids` so the backend binds them to the user message and forwards them to vLLM as `image_url` content blocks:

```bash
curl -N -X POST "https://air.changwon.ac.kr/simon/api/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "'"$CONV"'",
    "message": "Describe what you see in this picture.",
    "attachment_ids": ['"$ATT"']
  }'
```

The response is a custom SSE stream (`event: token`, `event: done`, `event: error`).

### Listing, fetching, deleting

```bash
# list every attachment in the conversation
curl -H "Authorization: Bearer $API_KEY" \
  "https://air.changwon.ac.kr/simon/api/conversations/$CONV/attachments"

# fetch raw image bytes (image attachments only; PDFs are stored as markdown)
curl -H "Authorization: Bearer $API_KEY" \
  "https://air.changwon.ac.kr/simon/api/conversations/$CONV/attachments/$ATT/raw" \
  -o photo.jpg

# delete an attachment (image file is reaped from disk if no other row references it)
curl -X DELETE -H "Authorization: Bearer $API_KEY" \
  "https://air.changwon.ac.kr/simon/api/conversations/$CONV/attachments/$ATT"
```

### Python example

```python
import httpx

API = "https://air.changwon.ac.kr/simon"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

with httpx.Client(headers=HEADERS, timeout=60) as c:
    conv = c.post(f"{API}/api/conversations").json()["id"]

    with open("photo.jpg", "rb") as f:
        att = c.post(
            f"{API}/api/conversations/{conv}/attachments",
            files={"file": ("photo.jpg", f, "image/jpeg")},
        ).json()

    with c.stream(
        "POST",
        f"{API}/api/chat/completions",
        json={
            "conversation_id": conv,
            "message": "What is in this image?",
            "attachment_ids": [att["id"]],
        },
    ) as r:
        for line in r.iter_lines():
            if line:
                print(line)
```

### Using the OpenAI-compatible `/v1` endpoint instead

If your client already speaks the OpenAI multimodal schema, you can skip the upload step and inline the image directly as a data URI or URL — the `/v1/chat/completions` route forwards multimodal payloads to vLLM as-is:

```bash
curl -X POST "https://air.changwon.ac.kr/simon/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-9B",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe this image."},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$(base64 -w0 photo.jpg)"'"}}
      ]
    }]
  }'
```

Note that the `/v1` path is stateless — there is no conversation history and no `attachment_ids` concept. PDF attachments are **not** supported on `/v1` (they only flow through the app `/api` routes that own the parser sidecar).

## OpenAI-Compatible API

For external tools and agents, use the OpenAI-compatible layer under `/v1`.

Public base URL:

- `https://air.changwon.ac.kr/simon/v1`

Implemented endpoints:

- `GET /v1/models`
- `POST /v1/chat/completions`

Authentication headers:

- `Authorization: Bearer <API_KEY>`
- or `X-API-Key: <API_KEY>`

### List Models

```bash
curl -H "Authorization: Bearer <API_KEY>" \
  https://air.changwon.ac.kr/simon/v1/models
```

### Chat Completion

```bash
curl -X POST "https://air.changwon.ac.kr/simon/v1/chat/completions" \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-9B",
    "messages": [
      {"role": "user", "content": "Hello"}
    ],
    "stream": false
  }'
```

### Streaming Chat Completion

```bash
curl -N -X POST "https://air.changwon.ac.kr/simon/v1/chat/completions" \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-9B",
    "messages": [
      {"role": "user", "content": "Reply with OK only."}
    ],
    "stream": true
  }'
```

## Using OpenCode or Other Agent Tools

Any client that can talk to an OpenAI-compatible endpoint can use this service.

For OpenCode, add a custom provider similar to this in `~/.config/opencode/opencode.json`:

```json
{
  "provider": {
    "simon": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "SIMON",
      "options": {
        "baseURL": "https://air.changwon.ac.kr/simon/v1"
      },
      "models": {
        "Qwen/Qwen3.5-9B": {
          "name": "Qwen 3.5 9B"
        }
      }
    }
  }
}
```

Then add the API key to OpenCode's credential store for the `simon` provider, or configure it through your preferred secret-management path.

Example run:

```bash
opencode run --model simon/Qwen/Qwen3.5-9B "Reply with OK only."
```

This repository has already been verified with OpenCode against the public `/simon/v1` endpoint.

## Health Check

Backend health endpoint:

```bash
curl http://localhost:8000/api/health
```

It reports:

- service status
- vLLM connectivity
- configured model id

## Notes

- the OpenAI-compatible surface currently focuses on `models` and `chat/completions`
- the browser app and the OpenAI-compatible API share the same account and API key system
- if you rotate or revoke a key, external tools must be updated accordingly

## License

This repository currently does not declare a separate license file.
