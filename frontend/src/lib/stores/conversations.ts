import { writable, derived } from "svelte/store";
import type { Conversation } from "$lib/api";

export const conversations = writable<Conversation[]>([]);
export const activeConversationId = writable<string | null>(null);
export const sidebarLoading = writable(false);
export const sidebarError = writable<string | null>(null);

export const activeConversation = derived(
    [conversations, activeConversationId],
    ([$conversations, $activeConversationId]) => {
        if (!$activeConversationId) return null;
        return $conversations.find((c) => c.id === $activeConversationId) ?? null;
    },
);

export function updateConversationInStore(updated: Conversation): void {
    conversations.update((list) =>
        list.map((c) => (c.id === updated.id ? updated : c)),
    );
}
