import { derived, writable } from "svelte/store";

import {
    ApiError,
    fetchCurrentUser,
    login as loginRequest,
    logout as logoutRequest,
    signup as signupRequest,
    type User,
} from "$lib/api";
import { chatError, isStreaming, messages, streamingContent, streamingReasoning } from "$lib/stores/chat";
import { activeConversationId, conversations, sidebarError, sidebarLoading } from "$lib/stores/conversations";

export const currentUser = writable<User | null>(null);
export const authLoading = writable(true);
export const authReady = writable(false);
export const authError = writable<string | null>(null);
export const isAuthenticated = derived(currentUser, ($currentUser) => $currentUser !== null);

function normalizeError(error: unknown): string {
    if (error instanceof ApiError) {
        return error.message;
    }
    if (error instanceof Error) {
        return error.message;
    }
    return "Unexpected network error";
}

function resetChatState(): void {
    conversations.set([]);
    activeConversationId.set(null);
    sidebarError.set(null);
    sidebarLoading.set(false);
    messages.set([]);
    chatError.set(null);
    isStreaming.set(false);
    streamingContent.set("");
    streamingReasoning.set("");
}

export async function initializeAuth(): Promise<void> {
    authLoading.set(true);
    authError.set(null);
    try {
        const session = await fetchCurrentUser();
        currentUser.set(session.user);
    } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
            currentUser.set(null);
            resetChatState();
        } else {
            authError.set(normalizeError(error));
        }
    } finally {
        authLoading.set(false);
        authReady.set(true);
    }
}

export async function signup(username: string, password: string): Promise<void> {
    authLoading.set(true);
    authError.set(null);
    try {
        const session = await signupRequest({ username, password });
        currentUser.set(session.user);
        resetChatState();
    } catch (error) {
        authError.set(normalizeError(error));
        throw error;
    } finally {
        authLoading.set(false);
        authReady.set(true);
    }
}

export async function login(username: string, password: string): Promise<void> {
    authLoading.set(true);
    authError.set(null);
    try {
        const session = await loginRequest({ username, password });
        currentUser.set(session.user);
        resetChatState();
    } catch (error) {
        authError.set(normalizeError(error));
        throw error;
    } finally {
        authLoading.set(false);
        authReady.set(true);
    }
}

export async function logout(): Promise<void> {
    authLoading.set(true);
    authError.set(null);
    try {
        await logoutRequest();
    } finally {
        currentUser.set(null);
        resetChatState();
        authLoading.set(false);
        authReady.set(true);
    }
}
