export interface ModelParams {
    temperature: number;
    max_tokens: number;
    top_p: number;
    enable_thinking: boolean;
}

export interface Conversation {
    id: string;
    title: string;
    system_prompt: string;
    model_params: ModelParams;
    created_at: string;
    updated_at: string;
}

export interface User {
    id: string;
    username: string;
    created_at: string;
}

export interface AuthSession {
    user: User;
}

export interface AuthCredentials {
    username: string;
    password: string;
}

export interface ApiKey {
    id: string;
    name: string;
    key_prefix: string;
    created_at: string;
    last_used_at: string | null;
    revoked_at: string | null;
}

export interface ApiKeyCreateResult {
    api_key: string;
    key: ApiKey;
}

export interface ConversationUpdate {
    title?: string;
    system_prompt?: string;
    model_params?: ModelParams;
}

export interface Message {
    id: number;
    conversation_id: string;
    role: "user" | "assistant" | "system";
    content: string;
    reasoning: string | null;
    created_at: string;
}

export interface ConversationDetail {
    conversation: Conversation;
    messages: Message[];
}

interface StreamingDelta {
    content?: string;
    reasoning?: string;
    reasoning_content?: string;
}

interface StreamingChoice {
    delta?: StreamingDelta;
}

interface StreamingChunk {
    choices?: StreamingChoice[];
    type?: string;
    conversation_id?: string;
    message?: string;
}

export interface StreamChatCompletionOptions {
    message: string;
    conversationId?: string;
    signal?: AbortSignal;
    onStart?: (conversationId: string) => void;
    onReasoningDelta?: (chunk: string) => void;
    onContentDelta?: (chunk: string) => void;
    onDone?: () => void;
    onError?: (message: string) => void;
}

function buildApiUrl(path: string): string {
    if (typeof window === "undefined") {
        return `/api${path}`;
    }

    const pathname = window.location.pathname;
    const basePath = pathname === "/" ? "" : pathname.replace(/\/+$/, "");
    return `${basePath}/api${path}`;
}

function parseStreamChunk(raw: string): StreamingChunk | null {
    try {
        return JSON.parse(raw) as StreamingChunk;
    } catch {
        return null;
    }
}

function processSseDataLine(rawPayload: string, options: StreamChatCompletionOptions): boolean {
    const payload = rawPayload.trim();
    if (!payload) {
        return false;
    }

    if (payload === "[DONE]") {
        options.onDone?.();
        return true;
    }

    const chunk = parseStreamChunk(payload);
    if (!chunk) {
        return false;
    }

    if (chunk.type === "start" && typeof chunk.conversation_id === "string") {
        options.onStart?.(chunk.conversation_id);
        return false;
    }

    if (chunk.type === "error") {
        options.onError?.(chunk.message ?? "Model is offline");
        return false;
    }

    const delta = chunk.choices?.[0]?.delta;
    if (!delta) {
        return false;
    }

    const reasoningChunk =
        typeof delta.reasoning === "string"
            ? delta.reasoning
            : typeof delta.reasoning_content === "string"
              ? delta.reasoning_content
              : "";
    if (reasoningChunk) {
        options.onReasoningDelta?.(reasoningChunk);
    }

    if (typeof delta.content === "string" && delta.content.length > 0) {
        options.onContentDelta?.(delta.content);
    }

    return false;
}

export class ApiError extends Error {
    constructor(
        public status: number,
        message: string,
    ) {
        super(message);
        this.name = "ApiError";
    }
}

async function handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
            const body = await response.json();
            if (body.detail) message = body.detail;
        } catch {
            /* empty */
        }
        throw new ApiError(response.status, message);
    }
    if (response.status === 204) {
        return undefined as T;
    }
    return response.json();
}

export async function fetchConversations(): Promise<Conversation[]> {
    const res = await fetch(buildApiUrl("/conversations"));
    return handleResponse<Conversation[]>(res);
}

export async function fetchCurrentUser(): Promise<AuthSession> {
    const res = await fetch(buildApiUrl("/auth/me"));
    return handleResponse<AuthSession>(res);
}

export async function signup(credentials: AuthCredentials): Promise<AuthSession> {
    const res = await fetch(buildApiUrl("/auth/signup"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
    });
    return handleResponse<AuthSession>(res);
}

export async function login(credentials: AuthCredentials): Promise<AuthSession> {
    const res = await fetch(buildApiUrl("/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
    });
    return handleResponse<AuthSession>(res);
}

export async function logout(): Promise<void> {
    const res = await fetch(buildApiUrl("/auth/logout"), {
        method: "POST",
    });
    return handleResponse<void>(res);
}

export async function fetchApiKeys(): Promise<ApiKey[]> {
    const res = await fetch(buildApiUrl("/auth/api-keys"));
    return handleResponse<ApiKey[]>(res);
}

export async function createApiKey(name: string): Promise<ApiKeyCreateResult> {
    const res = await fetch(buildApiUrl("/auth/api-keys"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
    });
    return handleResponse<ApiKeyCreateResult>(res);
}

export async function revokeApiKey(apiKeyId: string): Promise<void> {
    const res = await fetch(buildApiUrl(`/auth/api-keys/${apiKeyId}`), {
        method: "DELETE",
    });
    return handleResponse<void>(res);
}

export async function createConversation(): Promise<Conversation> {
    const res = await fetch(buildApiUrl("/conversations"), {
        method: "POST",
    });
    return handleResponse<Conversation>(res);
}

export async function updateConversation(
    id: string,
    update: ConversationUpdate,
): Promise<Conversation> {
    const res = await fetch(buildApiUrl(`/conversations/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(update),
    });
    return handleResponse<Conversation>(res);
}

export async function deleteConversation(id: string): Promise<void> {
    const res = await fetch(buildApiUrl(`/conversations/${id}`), {
        method: "DELETE",
    });
    return handleResponse<void>(res);
}

export async function fetchConversation(conversationId: string): Promise<ConversationDetail> {
    const res = await fetch(buildApiUrl(`/conversations/${conversationId}`));
    return handleResponse<ConversationDetail>(res);
}

export async function streamChatCompletion(options: StreamChatCompletionOptions): Promise<void> {
    const response = await fetch(buildApiUrl("/chat/completions"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            message: options.message,
            conversation_id: options.conversationId,
        }),
        signal: options.signal,
    });

    if (!response.ok) {
        let message = `Streaming request failed (${response.status})`;
        try {
            const body = (await response.json()) as { detail?: string };
            if (typeof body.detail === "string" && body.detail) {
                message = body.detail;
            }
        } catch {
            /* empty */
        }
        throw new ApiError(response.status, message);
    }

    if (!response.body) {
        throw new Error("Empty streaming response from server");
    }

    const decoder = new TextDecoder();
    const reader = response.body.getReader();
    let buffer = "";
    let done = false;

    while (!done) {
        const { value, done: streamDone } = await reader.read();
        done = streamDone;
        if (!value) {
            continue;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() ?? "";

        for (const line of lines) {
            if (!line.startsWith("data: ")) {
                continue;
            }

            const shouldStop = processSseDataLine(line.slice(6), options);
            if (shouldStop) {
                return;
            }
        }
    }

    const finalLine = buffer.trim();
    if (finalLine.startsWith("data: ")) {
        processSseDataLine(finalLine.slice(6), options);
    }
}
