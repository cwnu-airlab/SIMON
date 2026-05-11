<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# lib

## Purpose
Shared application code reachable through the `$lib` alias: typed REST/SSE client, Svelte components, Svelte stores, and static assets.

## Key Files
| File | Description |
|------|-------------|
| `api.ts` | Typed fetch client. Exports `ApiError`, types (`User`, `Conversation`, `Message`, `ApiKey`, …), and async functions (`fetchConversations`, `streamChatCompletion`, auth, API key management, conversation CRUD). `buildApiUrl()` derives the API base from `window.location.pathname` so the frontend works under subpaths like `/simon/` |
| `index.ts` | Documentation pointer: "place files you want to import through the `$lib` alias in this folder" |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `components/` | Svelte 5 UI components (see `components/AGENTS.md`) |
| `stores/` | Svelte stores for auth, chat, conversations, settings, UI (see `stores/AGENTS.md`) |
| `assets/` | Static assets imported by Svelte components (currently `favicon.svg`) |

## For AI Agents

### Working In This Directory
- All HTTP calls go through `api.ts` — do not hand-roll `fetch` calls in components. If you need a new endpoint, add a typed wrapper here first.
- `streamChatCompletion()` parses SSE manually (`response.body.getReader()`); it understands the custom `{"type":"start", conversation_id}` and `{"type":"error", message}` events on top of the standard OpenAI delta shape.
- `ApiError` carries an HTTP `status` field — auth-handling code in `stores/auth.ts` checks `error.status === 401` to clear local state without surfacing as a real error.
- `buildApiUrl()` returns `/api${path}` during SSR (no `window`); double-check any new API helper preserves that branch.

### Common Patterns
- Use camelCase for TypeScript identifiers, even when wrapping snake_case backend fields (`conversationId` vs `conversation_id`).
- Treat 204 responses as `undefined` (`handleResponse` already does this).
- Preserve the streaming buffer carry-over (`buffer = lines.pop() ?? ""`) so partially received SSE lines aren't dropped.

## Dependencies

### Internal
- Components and stores all import from `$lib/api` and from each other via `$lib/stores`.

### External
- Browser `fetch` and `TextDecoder`. SSR-safe: `typeof window === "undefined"` branch in `buildApiUrl`.

<!-- MANUAL: -->
