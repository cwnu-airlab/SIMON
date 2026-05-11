<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# routes

## Purpose
SvelteKit route tree. Currently a single-page application with a layout that owns the sidebar drawer, and one page that switches between the auth panel and the chat window based on `currentUser`.

## Key Files
| File | Description |
|------|-------------|
| `+layout.svelte` | Imports `app.css`, calls `initializeAuth()` once on mount, loads Inter + Material Symbols Outlined from Google Fonts, renders the `Sidebar` (slide-in on mobile, static on `lg:` and up) plus the page slot |
| `+page.svelte` | Top-level header (mobile menu button, conversation title, markdown toggle, settings button), conditional body — auth loading state → `AuthPanel` → `ChatWindow`. Owns `settingsOpen` local state for `SettingsPanel` |

## For AI Agents

### Working In This Directory
- `+layout.svelte` is the only place the auth bootstrap (`initializeAuth()`) runs — preserve the `onMount(() => { void initializeAuth(); })` call.
- `mobileSidebarOpen` from `$lib/stores/ui` controls the drawer; the layout switches to `position: static` at `min-width: 1024px` via `app.css` `.sidebar-drawer` rule. Keep both pieces in sync when redesigning the responsive layout.
- This SPA has no per-route data loaders. If you add `+page.ts` / `+page.server.ts`, ensure it doesn't double-fetch what `initializeAuth` already fetches.
- Add new routes as sibling folders with `+page.svelte` (and optional `+page.ts`); SvelteKit's file-based routing applies.

### Common Patterns
- Snippet-style children rendering: `let { children }: { children: Snippet } = $props();` then `{@render children()}`.
- Header layout uses Tailwind `flex` rows; mobile uses `sm:` and `lg:` modifiers throughout.

## Dependencies

### Internal
- `$lib/components/Sidebar.svelte`, `AuthPanel.svelte`, `ChatWindow.svelte`, `SettingsPanel.svelte`, `MarkdownToggle.svelte`.
- Stores: `$lib/stores/auth`, `$lib/stores/conversations`, `$lib/stores/ui`.

### External
- SvelteKit (`$app/environment` is used elsewhere; this folder uses standard Svelte 5 runes).

<!-- MANUAL: -->
