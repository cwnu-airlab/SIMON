import { writable } from "svelte/store";

import type { Message } from "$lib/api";

export const messages = writable<Message[]>([]);
export const isStreaming = writable(false);
export const streamingContent = writable("");
export const streamingReasoning = writable("");
export const chatError = writable<string | null>(null);
