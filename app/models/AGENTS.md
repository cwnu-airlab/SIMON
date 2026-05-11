<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# models

## Purpose
Pydantic v2 schemas for request bodies and response payloads. These are the public contract of the `/api/*` routes; the OpenAI-compatible `/v1/*` surface uses raw `dict[str, object]` and forwards to vLLM.

## Key Files
| File | Description |
|------|-------------|
| `auth.py` | `SignupRequest`, `LoginRequest`, `UserResponse`, `AuthSessionResponse`, `ApiKeyCreateRequest`, `ApiKeyResponse`, `ApiKeyCreateResponse` |
| `chat.py` | `ModelParams` (temperature/max_tokens/top_p/enable_thinking), `ChatMessage`, `ChatRequest`, `ConversationResponse`, `ConversationUpdate`, `MessageResponse` |
| `__init__.py` | Re-exports the public schema names for `from app.models import ...` |

## For AI Agents

### Working In This Directory
- Username pattern: `^[A-Za-z0-9_\-.]+$`, length 3–32. Password length 8–128. Keep the regex and bounds in sync between Pydantic and the DB column on `users.username` (UNIQUE COLLATE NOCASE).
- `ModelParams` field bounds (`temperature` 0.0–2.0, `top_p` 0.0–1.0, `max_tokens` 1–65536) must match `app/services/llm.py` request defaults.
- Add new exports to `__init__.py.__all__` so other modules can import via `from app.models import ...`.

### Testing Requirements
- Validation behavior is exercised through router tests — when adding constraints, also add a router-level test that asserts the 422 path.

### Common Patterns
- Use `Field(min_length=..., max_length=..., pattern=...)` for input validation; rely on default values for response models.
- Use `Literal[...]` for enum-like fields (e.g. `role`).
- Optional values use `T | None = None`, not `Optional[T]`.

## Dependencies

### Internal
- Consumed by `app/routers/*` (request parsing and `response_model`).

### External
- `pydantic`

<!-- MANUAL: -->
