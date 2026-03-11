<script lang="ts">
    import { fade, fly } from "svelte/transition";
    import { activeConversation, updateConversationInStore } from "$lib/stores/conversations";
    import { updateConversation, type ModelParams } from "$lib/api";

    const DEFAULTS: ModelParams = {
        temperature: 0.7,
        max_tokens: 4096,
        top_p: 0.9,
        enable_thinking: true,
    };

    interface Props {
        open: boolean;
        onclose: () => void;
    }

    let { open, onclose }: Props = $props();

    let systemPrompt = $state("");
    let temperature = $state(DEFAULTS.temperature);
    let maxTokens = $state(DEFAULTS.max_tokens);
    let topP = $state(DEFAULTS.top_p);
    let enableThinking = $state(DEFAULTS.enable_thinking);

    let saved = $state({
        systemPrompt: "",
        temperature: DEFAULTS.temperature,
        maxTokens: DEFAULTS.max_tokens,
        topP: DEFAULTS.top_p,
        enableThinking: DEFAULTS.enable_thinking,
    });

    let saving = $state(false);
    let error = $state<string | null>(null);
    let successMsg = $state<string | null>(null);

    let lastSyncedId: string | null = null;

    $effect(() => {
        const conv = $activeConversation;
        if (conv) {
            const isNewConv = conv.id !== lastSyncedId;
            lastSyncedId = conv.id;

            if (isNewConv) {
                error = null;
                successMsg = null;
                saving = false;
            }

            systemPrompt = conv.system_prompt;
            temperature = conv.model_params.temperature;
            maxTokens = conv.model_params.max_tokens;
            topP = conv.model_params.top_p;
            enableThinking = conv.model_params.enable_thinking;
            saved = {
                systemPrompt: conv.system_prompt,
                temperature: conv.model_params.temperature,
                maxTokens: conv.model_params.max_tokens,
                topP: conv.model_params.top_p,
                enableThinking: conv.model_params.enable_thinking,
            };
        } else {
            lastSyncedId = null;
        }
    });

    let tempValid = $derived(temperature >= 0 && temperature <= 2);
    let tokensValid = $derived(
        maxTokens != null && Number.isFinite(maxTokens) && maxTokens >= 1 && maxTokens <= 65536,
    );
    let topPValid = $derived(topP >= 0 && topP <= 1);
    let isValid = $derived(tempValid && tokensValid && topPValid);

    let hasChanges = $derived(
        systemPrompt !== saved.systemPrompt ||
            temperature !== saved.temperature ||
            maxTokens !== saved.maxTokens ||
            topP !== saved.topP ||
            enableThinking !== saved.enableThinking,
    );

    let canSave = $derived($activeConversation !== null && hasChanges && isValid && !saving);

    async function handleSave() {
        const conv = $activeConversation;
        if (!conv || !canSave) return;

        saving = true;
        error = null;
        successMsg = null;

        try {
            const updated = await updateConversation(conv.id, {
                system_prompt: systemPrompt,
                model_params: {
                    temperature: Math.round(temperature * 100) / 100,
                    max_tokens: Math.round(maxTokens),
                    top_p: Math.round(topP * 100) / 100,
                    enable_thinking: enableThinking,
                },
            });
            updateConversationInStore(updated);
            saved = { systemPrompt, temperature, maxTokens, topP, enableThinking };
            successMsg = "Settings saved";
            setTimeout(() => {
                successMsg = null;
            }, 2000);
        } catch (e) {
            error = e instanceof Error ? e.message : "Failed to save settings";
        } finally {
            saving = false;
        }
    }

    function handleReset() {
        systemPrompt = "";
        temperature = DEFAULTS.temperature;
        maxTokens = DEFAULTS.max_tokens;
        topP = DEFAULTS.top_p;
        enableThinking = DEFAULTS.enable_thinking;
        error = null;
        successMsg = null;
    }
</script>

{#if open}
    <!-- backdrop -->
    <div
        role="presentation"
        class="fixed inset-0 bg-black/30 z-40"
        transition:fade={{ duration: 150 }}
        onclick={onclose}
    ></div>

    <!-- panel -->
    <aside
        class="fixed right-0 top-0 h-full w-96 max-w-[90vw] bg-[var(--color-surface)] shadow-xl z-50 flex flex-col"
        transition:fly={{ x: 384, duration: 200 }}
    >
        <!-- header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
            <h2 class="text-lg font-semibold text-[var(--color-text)]">Settings</h2>
            <button
                onclick={onclose}
                class="p-1 rounded text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors"
                aria-label="Close settings"
            >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
            </button>
        </div>

        {#if !$activeConversation}
            <div class="flex-1 flex items-center justify-center p-6">
                <p class="text-sm text-[var(--color-text-secondary)] text-center">
                    Select a conversation to edit settings
                </p>
            </div>
        {:else}
            <!-- scrollable body -->
            <div class="flex-1 overflow-y-auto p-6 space-y-6">
                <!-- system prompt -->
                <section>
                    <label for="settings-system-prompt" class="block text-sm font-medium text-[var(--color-text)] mb-2">
                        System Prompt
                    </label>
                    <textarea
                        id="settings-system-prompt"
                        bind:value={systemPrompt}
                        placeholder="You are a helpful assistant..."
                        rows="4"
                        class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] text-sm resize-y focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
                    ></textarea>
                </section>

                <!-- model parameters -->
                <section class="space-y-4">
                    <h3 class="text-sm font-medium text-[var(--color-text)]">Model Parameters</h3>

                    <!-- temperature -->
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <label for="settings-temperature" class="text-[var(--color-text-secondary)]">
                                Temperature
                            </label>
                            <span
                                class="font-mono {tempValid ? 'text-[var(--color-text)]' : 'text-red-500'}"
                            >
                                {temperature.toFixed(2)}
                            </span>
                        </div>
                        <input
                            id="settings-temperature"
                            type="range"
                            min="0"
                            max="2"
                            step="0.05"
                            bind:value={temperature}
                            class="w-full accent-[var(--color-primary)]"
                        />
                        {#if !tempValid}
                            <p class="text-xs text-red-500 mt-1">Must be between 0 and 2</p>
                        {/if}
                    </div>

                    <!-- max tokens -->
                    <div>
                        <label for="settings-max-tokens" class="block text-sm text-[var(--color-text-secondary)] mb-1">
                            Max Tokens
                        </label>
                        <input
                            id="settings-max-tokens"
                            type="number"
                            min="1"
                            max="65536"
                            step="1"
                            bind:value={maxTokens}
                            class="w-full px-3 py-2 rounded-lg border text-sm font-mono bg-[var(--color-bg)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] {tokensValid ? 'border-[var(--color-border)]' : 'border-red-500'}"
                        />
                        {#if !tokensValid}
                            <p class="text-xs text-red-500 mt-1">Must be between 1 and 65,536</p>
                        {/if}
                    </div>

                    <!-- top p -->
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <label for="settings-top-p" class="text-[var(--color-text-secondary)]">Top P</label>
                            <span
                                class="font-mono {topPValid ? 'text-[var(--color-text)]' : 'text-red-500'}"
                            >
                                {topP.toFixed(2)}
                            </span>
                        </div>
                        <input
                            id="settings-top-p"
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            bind:value={topP}
                            class="w-full accent-[var(--color-primary)]"
                        />
                        {#if !topPValid}
                            <p class="text-xs text-red-500 mt-1">Must be between 0 and 1</p>
                        {/if}
                    </div>
                </section>

                <!-- thinking toggle -->
                <section>
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-sm font-medium text-[var(--color-text)]">Enable Thinking</p>
                            <p class="text-xs text-[var(--color-text-secondary)]">Slower but smarter reasoning</p>
                        </div>
                        <button
                            type="button"
                            onclick={() => (enableThinking = !enableThinking)}
                            class="relative w-11 h-6 rounded-full transition-colors {enableThinking ? 'bg-[var(--color-primary)]' : 'bg-gray-300'}"
                            role="switch"
                            aria-checked={enableThinking}
                            aria-label="Toggle thinking mode"
                        >
                            <span
                                class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform {enableThinking ? 'translate-x-5' : 'translate-x-0'}"
                            ></span>
                        </button>
                    </div>
                </section>

                <!-- reset -->
                <button
                    type="button"
                    onclick={handleReset}
                    class="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] underline transition-colors"
                >
                    Reset to defaults
                </button>
            </div>

            <!-- footer -->
            <div class="px-6 py-4 border-t border-[var(--color-border)] space-y-3">
                {#if error}
                    <div class="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                        {error}
                    </div>
                {/if}

                {#if successMsg}
                    <div class="px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
                        {successMsg}
                    </div>
                {/if}

                <button
                    type="button"
                    onclick={handleSave}
                    disabled={!canSave}
                    class="w-full py-2.5 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed {canSave ? 'bg-[var(--color-primary)] hover:opacity-90' : 'bg-gray-400'}"
                >
                    {#if saving}
                        <span class="inline-flex items-center justify-center gap-2">
                            <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            Saving...
                        </span>
                    {:else}
                        Save
                    {/if}
                </button>
            </div>
        {/if}
    </aside>
{/if}
