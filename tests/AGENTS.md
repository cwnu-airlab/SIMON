<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# tests

## Purpose
Pytest suite for the FastAPI backend.

## Key Files
| File | Description |
|------|-------------|
| `test_collab_push_smoke.py` | Smoke test added to verify collaborator push permissions (`unittest.TestCase`, asserts `"simon".upper() == "SIMON"`) |

## For AI Agents

### Working In This Directory
- Test discovery runs against `tests/` from repo root: `uv run pytest tests/ -v`.
- The current suite is sparse — when adding real tests, prefer `pytest`-style functions over `unittest.TestCase` for consistency with the rest of the Python ecosystem, unless extending an existing `TestCase`.
- For DB-dependent tests, override `DATABASE_PATH` to a tempfile and call `app.database.init_db()` in a fixture; do not write to `data/chat.db`.
- For HTTP tests of routers, use `httpx.AsyncClient(transport=ASGITransport(app=app))` so the lifespan/`http_client` is initialized.
- For vLLM-touching code paths, mock `httpx.AsyncClient.stream` / `.request` rather than depending on a live model server.

### Testing Requirements
- Run all: `uv run pytest tests/ -v`
- Single test: `uv run pytest tests/test_collab_push_smoke.py::TestCollaboratorPushSmoke::test_branch_push_smoke -v`
- Coverage: `uv run pytest tests/ --cov=app --cov-report=html`

### Common Patterns
- Async tests should use `pytest-asyncio` (not yet a declared dev dep — add it before introducing `async def` tests).

## Dependencies

### Internal
- The application package under `app/`.

### External
- `pytest` (declared as a dev dep in the future; currently not pinned — add to `pyproject.toml` `[project.optional-dependencies].dev` when introduced).

<!-- MANUAL: -->
