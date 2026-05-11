<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# src

## Purpose
SvelteKit application source: HTML shell, global styles, route entry points, shared UI library, and TypeScript ambient types.

## Key Files
| File | Description |
|------|-------------|
| `app.html` | HTML shell with `%sveltekit.head%` / `%sveltekit.body%` placeholders. `data-sveltekit-preload-data="hover"` enables hover-preload navigation |
| `app.css` | Global styles: Tailwind 4 import, typography plugin, CSS-variable color palette (`--color-primary`, `--color-bg`, etc.), Material Symbols variation settings, sidebar drawer responsive override at `min-width: 1024px` |
| `app.d.ts` | Empty `App` namespace declarations (ambient types for SvelteKit) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `lib/` | Shared `$lib`-aliased code: API client, components, stores, assets (see `lib/AGENTS.md`) |
| `routes/` | SvelteKit route tree (see `routes/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Add global CSS variables and base styles to `app.css`. Component-scoped styles belong inside `<style>` blocks in their `.svelte` files.
- The active color palette is centered on `--color-primary: #005a9a` (note: the README's "Imperial Blue #104486" is the brand spec; the runtime uses `#005a9a`). Update both if rebranding.
- Sidebar responsive behavior depends on the `.sidebar-drawer` class plus the `lg:` breakpoint media query in `app.css`. Don't override `transform` on `.sidebar-drawer` from inline styles when on desktop.
- Keep `app.d.ts` updated when introducing typed `Locals`, `PageData`, or `Platform` (currently all commented placeholders).

### Common Patterns
- `Inter` and `Material Symbols Outlined` are loaded from Google Fonts in `routes/+layout.svelte` (not in `app.html`).
- Use `$lib/...` imports rather than relative paths into `lib/`.

## Dependencies

### Internal
- Routes consume components from `$lib/components/` and stores from `$lib/stores/`.

### External
- Tailwind CSS 4 (via `app.css` `@import "tailwindcss"`).

<!-- MANUAL: -->
