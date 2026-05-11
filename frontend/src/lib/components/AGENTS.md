<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# components

## Purpose
Svelte 5 UI components composing the SIMON web app: chat surface, sidebar/conversation list, auth panel, settings/API-key modals, and markdown rendering.

## Key Files
| File | Description |
|------|-------------|
| `Sidebar.svelte` | Conversation list, new-chat button, mobile drawer integration, account/sign-out menu |
| `AuthPanel.svelte` | Login + signup forms shown when `currentUser` is null |
| `ChatWindow.svelte` | Message list, streaming bubble, scroll management, error banner; loads conversation attachments on switch and renders `<AttachmentChips />` above the input |
| `ChatInput.svelte` | Composer textarea + send button + attach button accepting PDF or PNG/JPEG/WebP (10MB image / 50MB PDF client-side caps). Images go to `pendingMessageAttachments` and render as thumbnails above the input until send; PDFs go to `conversationAttachments`. `uploadAttachment` handles progress |
| `AttachmentChips.svelte` | Renders the active conversation's attachment list as removable chips and the in-flight upload progress chip |
| `MessageBubble.svelte` | Renders one user/assistant message; uses `MarkdownRenderer` when markdown is enabled. For user messages with image attachments, renders `<img>` thumbnails (clickable to full-size) above the text bubble using `attachmentRawUrl()` |
| `MarkdownRenderer.svelte` | `marked` + `dompurify` + `highlight.js` + KaTeX pipeline |
| `MarkdownToggle.svelte` | Header toggle bound to the `markdownEnabled` store |
| `ThinkingCollapsible.svelte` | Collapsible block that displays the `reasoning` portion of an assistant message |
| `SettingsPanel.svelte` | Slide-in panel for per-conversation system prompt and `ModelParams` |
| `ApiKeysModal.svelte` | Modal to list / create / revoke personal API keys |

## For AI Agents

### Working In This Directory
- These components use Svelte 5 runes: `$state`, `$props`, `$derived`, `$effect`. Do not mix in legacy reactivity.
- Component props are destructured from `$props()` and typed inline, e.g. `let { open, onclose }: { open: boolean; onclose: () => void } = $props();`.
- Mobile sidebar visibility is driven by the `mobileSidebarOpen` store from `$lib/stores/ui` — toggle it via `toggleMobileSidebar()` rather than mutating local state.
- Any model output that's rendered as HTML must go through `MarkdownRenderer.svelte` (which sanitizes via dompurify). Never bind raw model content to `{@html ...}` directly.
- Auto-scroll in `ChatWindow.svelte` should remain pinned to the bottom while streaming; preserve the streaming-content/streaming-reasoning subscription pattern.

### Testing Requirements
- No component test setup exists yet. Type-check with `npm run check`. For visual changes start the dev server (`npm run dev`) and exercise the affected flow.

### Common Patterns
- Tailwind utility-first styling with the CSS-variable palette from `app.css` (`bg-[var(--color-bg-light)]`, etc.).
- Material Symbols icons via `<span class="material-symbols-outlined">name</span>`.
- Components subscribe to stores with the `$store` prefix (`$currentUser`, `$activeConversation`, `$messages`).

## Dependencies

### Internal
- `$lib/api` for typed REST/SSE calls.
- `$lib/stores/*` for shared state.

### External
- `marked`, `marked-highlight`, `marked-katex-extension`, `highlight.js`, `katex`, `dompurify`/`isomorphic-dompurify`.

<!-- MANUAL: -->
