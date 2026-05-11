<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# frontend

## Purpose
SvelteKit 2 / Svelte 5 web UI for SIMON. Built with `@sveltejs/adapter-node` and served by the `frontend` Docker service. Talks to the FastAPI backend through the inner nginx proxy at `/api/*` (and proxies `/api` to `localhost:8000` in dev via `vite.config.ts`).

## Key Files
| File | Description |
|------|-------------|
| `package.json` | Scripts (`dev`, `build`, `preview`, `check`), Svelte 5 / SvelteKit 2 / Tailwind 4 / marked / dompurify / highlight.js / katex |
| `package-lock.json` | npm lock file |
| `svelte.config.js` | Configures `@sveltejs/adapter-node` |
| `vite.config.ts` | Dev proxy: `/api` → `http://localhost:8000` |
| `tsconfig.json` | TypeScript settings (extends SvelteKit defaults) |
| `postcss.config.js` | PostCSS pipeline (Tailwind 4 via `@tailwindcss/postcss`) |
| `Dockerfile` | Two-stage build: `node:22-slim` builder → minimal runtime image running `node build` |
| `README.md` | SvelteKit's default README (npm scripts overview) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `src/` | App source — routes, components, stores, API client (see `src/AGENTS.md`) |
| `static/` | Static assets served at root (currently `robots.txt`) |
| `build/` | Production output from `npm run build` (gitignored) |
| `node_modules/` | npm dependencies (gitignored) |
| `.svelte-kit/` | SvelteKit-generated artifacts (gitignored) |
| `.vscode/` | Editor configuration |

## For AI Agents

### Working In This Directory
- Run from this directory, not the repo root: `npm run dev`, `npm run check`, `npm run build`.
- This project uses **Svelte 5 runes** (`$state`, `$props`, `$derived`) — do not introduce legacy `export let` or `$:` reactive statements in new code.
- Tailwind 4 is configured via PostCSS, not a `tailwind.config.js`. Custom design tokens are CSS variables in `src/app.css`.
- The API client (`src/lib/api.ts`) builds URLs with `buildApiUrl()` — it derives a basepath from `window.location.pathname` so the app works under subpath deployments like `/simon/`. Always go through this helper for backend calls.
- Markdown rendering uses `marked` + `dompurify` (`isomorphic-dompurify` for SSR) + `highlight.js` + KaTeX. Sanitize before injecting any model output.

### Testing Requirements
- Type-check: `npm run check` (runs `svelte-kit sync` then `svelte-check`).
- Production build sanity: `npm run build`.
- No JS test runner is configured yet — when adding tests, prefer Vitest because it shares Vite config.

### Common Patterns
- One Svelte component per file under `src/lib/components/`.
- Stores in `src/lib/stores/` are re-exported via `src/lib/stores/index.ts`.
- All cross-cutting reset logic for sign-in/sign-out is centralized in `src/lib/stores/auth.ts` (`resetChatState`).

## Dependencies

### Internal
- The backend's `/api/*` endpoints — see `app/routers/`.

### External
- See `package.json`. Notable: `svelte@^5.51`, `@sveltejs/kit@^2.50`, `@sveltejs/adapter-node@^5.5`, `tailwindcss@^4.2`, `marked@^17`, `dompurify@^3.3`, `highlight.js@^11`, `katex@^0.16`.

<!-- MANUAL: -->
