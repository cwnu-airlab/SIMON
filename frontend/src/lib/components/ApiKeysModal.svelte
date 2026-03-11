<script lang="ts">
    import { onDestroy } from "svelte";
    import { fade, fly } from "svelte/transition";

    import {
        createApiKey,
        fetchApiKeys,
        revokeApiKey,
        type ApiKey,
    } from "$lib/api";
    import { currentUser } from "$lib/stores/auth";

    const REVOCATION_GRACE_MS = 5 * 60 * 1000;

    interface Props {
        open: boolean;
        onclose: () => void;
    }

    let { open, onclose }: Props = $props();

    let apiKeys = $state<ApiKey[]>([]);
    let apiKeysLoading = $state(false);
    let apiKeysError = $state<string | null>(null);
    let apiKeyName = $state("");
    let creatingApiKey = $state(false);
    let revokingApiKeyId = $state<string | null>(null);
    let newApiKeyValue = $state<string | null>(null);
    let copiedApiKey = $state(false);
    let lastLoadedUserId: string | null = null;

    const removalTimers = new Map<string, ReturnType<typeof setTimeout>>();

    function clearRemovalTimer(apiKeyId: string): void {
        const timer = removalTimers.get(apiKeyId);
        if (timer) {
            clearTimeout(timer);
            removalTimers.delete(apiKeyId);
        }
    }

    function clearAllRemovalTimers(): void {
        for (const timer of removalTimers.values()) {
            clearTimeout(timer);
        }
        removalTimers.clear();
    }

    function removeExpiredRevokedKeys(keys: ApiKey[]): ApiKey[] {
        const now = Date.now();
        return keys.filter((key) => {
            if (!key.revoked_at) {
                return true;
            }

            const revokedAt = new Date(key.revoked_at).getTime();
            return Number.isNaN(revokedAt) || revokedAt + REVOCATION_GRACE_MS > now;
        });
    }

    function syncRemovalTimers(keys: ApiKey[]): void {
        const visibleIds = new Set(keys.map((key) => key.id));
        for (const apiKeyId of removalTimers.keys()) {
            if (!visibleIds.has(apiKeyId)) {
                clearRemovalTimer(apiKeyId);
            }
        }

        for (const key of keys) {
            clearRemovalTimer(key.id);
            if (!key.revoked_at) {
                continue;
            }

            const revokedAt = new Date(key.revoked_at).getTime();
            if (Number.isNaN(revokedAt)) {
                continue;
            }

            const removeIn = revokedAt + REVOCATION_GRACE_MS - Date.now();
            if (removeIn <= 0) {
                apiKeys = apiKeys.filter((candidate) => candidate.id !== key.id);
                continue;
            }

            removalTimers.set(
                key.id,
                setTimeout(() => {
                    apiKeys = apiKeys.filter((candidate) => candidate.id !== key.id);
                    removalTimers.delete(key.id);
                }, removeIn),
            );
        }
    }

    async function loadApiKeys(force = false): Promise<void> {
        const userId = $currentUser?.id ?? null;
        if (!userId) {
            apiKeys = [];
            apiKeysError = null;
            lastLoadedUserId = null;
            clearAllRemovalTimers();
            return;
        }

        if (!force && lastLoadedUserId === userId && apiKeys.length > 0) {
            return;
        }

        apiKeysLoading = true;
        apiKeysError = null;
        try {
            const loadedKeys = removeExpiredRevokedKeys(await fetchApiKeys());
            apiKeys = loadedKeys;
            lastLoadedUserId = userId;
            syncRemovalTimers(loadedKeys);
        } catch (error) {
            apiKeysError = error instanceof Error ? error.message : "Failed to load API keys";
        } finally {
            apiKeysLoading = false;
        }
    }

    async function handleCreateApiKey(): Promise<void> {
        const name = apiKeyName.trim();
        if (!name) {
            return;
        }

        creatingApiKey = true;
        apiKeysError = null;
        copiedApiKey = false;

        try {
            const result = await createApiKey(name);
            apiKeys = [result.key, ...apiKeys];
            apiKeyName = "";
            newApiKeyValue = result.api_key;
            syncRemovalTimers(apiKeys);
        } catch (error) {
            apiKeysError = error instanceof Error ? error.message : "Failed to create API key";
        } finally {
            creatingApiKey = false;
        }
    }

    async function handleRevokeApiKey(apiKeyId: string): Promise<void> {
        revokingApiKeyId = apiKeyId;
        apiKeysError = null;
        try {
            await revokeApiKey(apiKeyId);
            const revokedAt = new Date().toISOString();
            apiKeys = apiKeys.map((key) =>
                key.id === apiKeyId ? { ...key, revoked_at: revokedAt } : key,
            );
            syncRemovalTimers(apiKeys);
        } catch (error) {
            apiKeysError = error instanceof Error ? error.message : "Failed to revoke API key";
        } finally {
            revokingApiKeyId = null;
        }
    }

    async function copyNewApiKey(): Promise<void> {
        if (!newApiKeyValue || !navigator.clipboard) {
            return;
        }

        await navigator.clipboard.writeText(newApiKeyValue);
        copiedApiKey = true;
    }

    $effect(() => {
        const userId = $currentUser?.id ?? null;
        if (!userId) {
            apiKeys = [];
            apiKeysError = null;
            apiKeyName = "";
            newApiKeyValue = null;
            copiedApiKey = false;
            lastLoadedUserId = null;
            clearAllRemovalTimers();
            return;
        }

        if (open && lastLoadedUserId !== userId) {
            void loadApiKeys(true);
        }
    });

    $effect(() => {
        if (open) {
            void loadApiKeys();
        }
    });

    onDestroy(() => {
        clearAllRemovalTimers();
    });
</script>

{#if open}
    <div
        role="presentation"
        class="fixed inset-0 z-40 bg-black/30"
        transition:fade={{ duration: 150 }}
        onclick={onclose}
    ></div>

    <aside
        class="fixed right-0 top-0 z-50 flex h-full w-[28rem] max-w-[92vw] flex-col bg-[var(--color-surface)] shadow-xl"
        transition:fly={{ x: 448, duration: 200 }}
    >
        <div class="border-b border-[var(--color-border)] px-6 py-4">
            <div class="flex items-center justify-between gap-4">
                <div>
                    <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-secondary)]">
                        Developer Access
                    </p>
                    <h2 class="mt-1 text-lg font-semibold text-[var(--color-text)]">API Keys</h2>
                    <p class="mt-1 text-sm text-[var(--color-text-secondary)]">
                        Create tokens for scripts and external clients. Revoked keys disappear after 5 minutes.
                    </p>
                </div>
                <button
                    onclick={onclose}
                    class="rounded p-1 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text)]"
                    aria-label="Close API keys"
                >
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
        </div>

        <div class="flex-1 overflow-y-auto px-6 py-5">
            <section class="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <label for="api-key-name" class="mb-2 block text-sm font-medium text-[var(--color-text)]">
                    Create New Key
                </label>
                <div class="flex gap-2">
                    <input
                        id="api-key-name"
                        bind:value={apiKeyName}
                        class="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-[#104486] focus:ring-2 focus:ring-[#104486]/15"
                        placeholder="e.g. deployment script"
                        maxlength="50"
                    />
                    <button
                        type="button"
                        onclick={() => void handleCreateApiKey()}
                        disabled={creatingApiKey || !apiKeyName.trim()}
                        class="rounded-xl bg-[#104486] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#0c3366] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {creatingApiKey ? "Creating..." : "Create"}
                    </button>
                </div>
            </section>

            {#if newApiKeyValue}
                <section class="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                    <p class="text-xs font-semibold uppercase tracking-[0.1em] text-amber-800">Copy this now</p>
                    <p class="mt-1 text-sm text-amber-800/80">The full key is shown only once.</p>
                    <code class="mt-3 block overflow-x-auto rounded-xl bg-white px-3 py-3 text-[11px] text-slate-700">{newApiKeyValue}</code>
                    <button
                        type="button"
                        onclick={() => void copyNewApiKey()}
                        class="mt-3 rounded-lg border border-amber-300 px-3 py-1.5 text-xs font-medium text-amber-900 transition hover:bg-white"
                    >
                        {copiedApiKey ? "Copied" : "Copy key"}
                    </button>
                </section>
            {/if}

            {#if apiKeysError}
                <div class="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {apiKeysError}
                </div>
            {/if}

            <section class="mt-5 space-y-3">
                <div class="flex items-center justify-between">
                    <h3 class="text-sm font-semibold text-[var(--color-text)]">Issued Keys</h3>
                    <span class="text-xs text-[var(--color-text-secondary)]">{$currentUser?.username}</span>
                </div>

                {#if apiKeysLoading}
                    <p class="text-sm text-slate-400">Loading API keys...</p>
                {:else if apiKeys.length === 0}
                    <div class="rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-400">
                        No API keys yet.
                    </div>
                {:else}
                    <div class="space-y-3">
                        {#each apiKeys as key (key.id)}
                            <div class="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                                <div class="flex items-start justify-between gap-3">
                                    <div class="min-w-0">
                                        <p class="truncate text-sm font-semibold text-slate-800">{key.name}</p>
                                        <p class="mt-1 font-mono text-[11px] text-slate-400">{key.key_prefix}...</p>
                                        <p class="mt-2 text-[11px] leading-5 text-slate-400">
                                            Created {new Date(key.created_at).toLocaleString()}
                                            {#if key.last_used_at}
                                                <br />
                                                Last used {new Date(key.last_used_at).toLocaleString()}
                                            {/if}
                                            {#if key.revoked_at}
                                                <br />
                                                Deleting soon · revoked {new Date(key.revoked_at).toLocaleTimeString()}
                                            {/if}
                                        </p>
                                    </div>

                                    {#if key.revoked_at}
                                        <span class="rounded-full bg-slate-200 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                                            Revoked
                                        </span>
                                    {:else}
                                        <button
                                            type="button"
                                            onclick={() => void handleRevokeApiKey(key.id)}
                                            disabled={revokingApiKeyId === key.id}
                                            class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                            {revokingApiKeyId === key.id ? "Revoking..." : "Revoke"}
                                        </button>
                                    {/if}
                                </div>
                            </div>
                        {/each}
                    </div>
                {/if}
            </section>
        </div>
    </aside>
{/if}
