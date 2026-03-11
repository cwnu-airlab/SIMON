# SIMON

SIMON is a self-hosted chat service built on top of FastAPI, SvelteKit, SQLite, and vLLM.

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
- Docker Compose deployment with backend, frontend, and nginx

## Stack

- Backend: FastAPI, httpx, aiosqlite, pydantic-settings
- Frontend: SvelteKit 2, Svelte 5, Tailwind CSS 4
- Model backend: vLLM
- Database: SQLite
- Runtime: Docker Compose

## Repository Layout

- `app/` - FastAPI backend
- `frontend/` - SvelteKit frontend
- `nginx/default.conf` - internal nginx routing for Compose deployment
- `docker-compose.yml` - production-style multi-container deployment
- `Dockerfile` - backend image
- `frontend/Dockerfile` - frontend image
- `tutorial.md` - OpenCode setup guide for first-time users
- `tutorial.ko.md` - Korean OpenCode setup guide

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
VLLM_BASE_URL=http://host.docker.internal:7777
VLLM_MODEL=Qwen/Qwen3.5-9B
DATABASE_PATH=data/chat.db
SESSION_COOKIE_SECURE=true
ORIGIN=https://air.changwon.ac.kr
```

Important settings:

- `VLLM_BASE_URL` - upstream vLLM server
- `VLLM_MODEL` - default model exposed by the service
- `DATABASE_PATH` - SQLite database path
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
- `POST /api/chat/completions`

The app chat endpoint is intended for the web UI and uses the service's custom SSE event shape.

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
