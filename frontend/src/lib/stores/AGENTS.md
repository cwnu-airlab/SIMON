<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# stores

## Purpose
Svelte writable / derived stores plus side-effect helpers that hold the frontend's runtime state: authenticated user, conversation list, active conversation, streaming message buffers, persistent settings, and mobile-sidebar UI flag.

## Key Files
| File | Description |
|------|-------------|
| `auth.ts` | `currentUser`, `authLoading`, `authReady`, `authError`, derived `isAuthenticated`. Async helpers `initializeAuth`, `signup`, `login`, `logout`. Centralizes `resetChatState()` which wipes conversations/messages/streaming buffers, attachments stores, and closes the mobile sidebar |
| `attachments.ts` | `conversationAttachments` (PDFs that survive every turn), `pendingMessageAttachments` (images attached to the user message currently being composed; cleared on send), `uploadingAttachment` (`{filename, progress}` or null), `attachmentError`. `resetAttachments()` clears all four — used inside `auth.resetChatState()` |
| `conversations.ts` | `conversations`, `activeConversationId`, `sidebarLoading`, `sidebarError`, derived `activeConversation`, helper `updateConversationInStore` |
| `chat.ts` | `messages`, `isStreaming`, `streamingContent`, `streamingReasoning`, `chatError` — buffers used during a live SSE response |
| `settings.ts` | `markdownEnabled` writable, persisted to `localStorage` under `simon_markdown_enabled`. SSR-safe via `browser` guard |
| `ui.ts` | `mobileSidebarOpen` plus `openMobileSidebar` / `closeMobileSidebar` / `toggleMobileSidebar` |
| `index.ts` | Re-exports every store module so consumers can `import { ... } from "$lib/stores"` |

## For AI Agents

### Working In This Directory
- When adding a sign-in/sign-out flow, route the reset through `resetChatState()` in `auth.ts` so every dependent store is cleared in one place.
- `markdownEnabled` initializes from `localStorage`; the subscription that writes back to `localStorage` only runs `if (browser)` — keep both branches when changing the persistence layer.
- Don't import stores into `+layout.svelte` / `+page.svelte` lazily — top-level imports are fine because the SvelteKit module graph handles SSR safely (writables are constructed once per request).
- Re-export any new store from `index.ts` to keep the import surface tidy.
- `activeConversation` is a derived store — don't try to write to it; mutate `conversations` and/or `activeConversationId` instead.

### Common Patterns
- One file per concern; cross-store coupling lives in helper functions inside `auth.ts`.
- Cycle-aware imports: `auth.ts` imports from the other stores; the others stay leaf modules.

## Dependencies

### Internal
- `$lib/api` for types (`User`, `Conversation`, `Message`, `ApiKey`) and request functions.
- `$app/environment` for the `browser` guard.

### External
- `svelte/store` (`writable`, `derived`).

<!-- MANUAL: -->
