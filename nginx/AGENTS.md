<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# nginx

## Purpose
Reverse-proxy configuration consumed by the `nginx:alpine` container in `docker-compose.yml`. Splits incoming traffic on a single host port (default `3080`) between the FastAPI backend and the SvelteKit frontend.

## Key Files
| File | Description |
|------|-------------|
| `default.conf` | Single `server` block with three locations: `/api/` and `/v1/` → `backend:8000`, everything else → `frontend:3000`. SSE-friendly settings (`proxy_buffering off`, `proxy_cache off`, 300s read/send timeouts, chunked transfer) on both backend locations |

## For AI Agents

### Working In This Directory
- Both `/api/` and `/v1/` MUST have streaming-friendly settings (`proxy_buffering off`, `proxy_cache off`, `X-Accel-Buffering` is also set on the FastAPI side). Removing any of these will break SSE chat streaming.
- The `/` location forwards WebSocket upgrade headers (`Upgrade`, `Connection`) for SvelteKit HMR / live-reload in dev-style deployments.
- After editing this file rerun `docker compose restart nginx` (the volume is mounted read-only, so the container picks up the new file on restart but does not hot-reload).
- When deploying behind an outer proxy under a subpath like `/simon/`, the outer proxy must strip the prefix before forwarding to port `3080`. This nginx config receives unprefixed paths.

### Testing Requirements
- After changes: `docker compose up -d --build && docker compose logs -f nginx`, then verify `/api/health` and `/v1/models` both respond and that streaming chat works (chunks arrive incrementally).

### Common Patterns
- `client_max_body_size 10M;` is set globally in the server block — bump it if you need to accept larger payloads.
- Use named upstreams (`upstream backend { server backend:8000; }`) so service hostnames match the Compose service names.

## Dependencies

### Internal
- Compose services `backend` (FastAPI) and `frontend` (SvelteKit / `node build`).

### External
- `nginx:alpine` Docker image.

<!-- MANUAL: -->
