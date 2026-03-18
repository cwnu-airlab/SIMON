<script lang="ts">
    import ApiKeysModal from "$lib/components/ApiKeysModal.svelte";
    import {
        createConversation,
        deleteConversation,
        fetchConversations,
        updateConversation,
    } from "$lib/api";
    import {
        conversations,
        activeConversationId,
        sidebarLoading,
        sidebarError,
    } from "$lib/stores/conversations";
    import {
        authLoading,
        currentUser,
        isAuthenticated,
        logout,
    } from "$lib/stores/auth";
    import { closeMobileSidebar } from "$lib/stores/ui";

    let renamingId: string | null = $state(null);
    let renameValue: string = $state("");
    let renameInput: HTMLInputElement | undefined = $state(undefined);
    let loadedUserId: string | null = $state(null);
    let apiKeysModalOpen = $state(false);

    async function loadConversations() {
        if (!$currentUser) {
            $conversations = [];
            $activeConversationId = null;
            loadedUserId = null;
            return;
        }

        $sidebarLoading = true;
        $sidebarError = null;
        try {
            $conversations = await fetchConversations();
            loadedUserId = $currentUser.id;
            if (!$activeConversationId && $conversations.length > 0) {
                $activeConversationId = $conversations[0].id;
            }
        } catch (e) {
            $sidebarError =
                e instanceof Error ? e.message : "Failed to load conversations";
        } finally {
            $sidebarLoading = false;
        }
    }

    async function handleNewChat() {
        if (!$currentUser) {
            return;
        }
        try {
            const created = await createConversation();
            $conversations = [created, ...$conversations];
            $activeConversationId = created.id;
            closeMobileSidebar();
        } catch (e) {
            $sidebarError =
                e instanceof Error ? e.message : "Failed to create conversation";
        }
    }

    async function handleDelete(id: string) {
        if (!$currentUser) {
            return;
        }
        try {
            await deleteConversation(id);
            $conversations = $conversations.filter((c) => c.id !== id);
            if ($activeConversationId === id) {
                $activeConversationId =
                    $conversations.length > 0 ? $conversations[0].id : null;
            }
        } catch (e) {
            $sidebarError =
                e instanceof Error ? e.message : "Failed to delete conversation";
        }
    }

    function startRename(id: string, currentTitle: string) {
        renamingId = id;
        renameValue = currentTitle;
        requestAnimationFrame(() => renameInput?.focus());
    }

    async function submitRename() {
        if (!renamingId || !renameValue.trim()) {
            renamingId = null;
            return;
        }
        try {
            const updated = await updateConversation(renamingId, {
                title: renameValue.trim(),
            });
            $conversations = $conversations.map((c) =>
                c.id === updated.id ? updated : c,
            );
        } catch (e) {
            $sidebarError =
                e instanceof Error ? e.message : "Failed to rename conversation";
        } finally {
            renamingId = null;
        }
    }

    function handleRenameKeydown(e: KeyboardEvent) {
        if (e.key === "Enter") submitRename();
        if (e.key === "Escape") renamingId = null;
    }

    function handleSelectConversation(id: string) {
        $activeConversationId = id;
        closeMobileSidebar();
    }

    async function handleLogout() {
        await logout();
        closeMobileSidebar();
    }

    $effect(() => {
        if (!$isAuthenticated) {
            $conversations = [];
            $activeConversationId = null;
            loadedUserId = null;
            apiKeysModalOpen = false;
            return;
        }

        const userId = $currentUser?.id ?? null;
        if (userId && loadedUserId !== userId) {
            void loadConversations();
        }
    });
</script>

<aside class="flex h-full w-full flex-col overflow-hidden border-r border-slate-200 bg-white shadow-xl lg:shadow-none">
    <!-- Header -->
    <div class="flex items-center justify-between gap-3 bg-[#005a9a] px-5 py-4 text-white shrink-0 lg:px-6">
        <div class="flex items-center gap-3 min-w-0">
            <span class="material-symbols-outlined !text-[24px] shrink-0">forum</span>
            <h1 class="truncate text-xl font-bold tracking-tight">SIMON</h1>
        </div>
        <button
            type="button"
            class="rounded-lg p-1 text-white/80 transition hover:bg-white/10 hover:text-white lg:hidden"
            aria-label="Close navigation"
            onclick={closeMobileSidebar}
        >
            <span class="material-symbols-outlined !text-[20px]">close</span>
        </button>
    </div>

    <!-- New Chat Button -->
    <div class="border-b border-slate-200 p-3 shrink-0 sm:p-4">
        <button
            onclick={handleNewChat}
            disabled={!$isAuthenticated || $authLoading}
            class="w-full bg-[#9BC2F9] hover:bg-[#8ab6f4] text-[#005a9a] font-semibold py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 transition-colors cursor-pointer"
        >
            <span class="material-symbols-outlined !text-[20px]">add</span>
            <span>New Chat</span>
        </button>
    </div>

    <!-- Conversation List -->
    <nav class="flex-1 overflow-y-auto py-2">
        {#if $authLoading}
            <div class="px-4 py-3 text-sm text-slate-400">Checking account...</div>
        {:else if !$isAuthenticated}
            <div class="px-6 py-12 text-center">
                <span class="material-symbols-outlined text-3xl text-slate-300 mb-2">lock</span>
                <p class="text-sm text-slate-500">Sign in to access your private conversations.</p>
            </div>
        {:else if $sidebarLoading}
            <div class="px-4 py-3 text-sm text-slate-400">Loading...</div>
        {:else if $sidebarError}
            <div class="px-4 py-3">
                <p class="text-sm text-red-500 mb-2">{$sidebarError}</p>
                <button
                    onclick={loadConversations}
                    class="text-xs text-slate-500 underline hover:text-slate-700 cursor-pointer"
                >
                    Retry
                </button>
            </div>
        {:else if $conversations.length === 0}
            <div class="flex flex-col items-center justify-center px-6 py-12 text-center">
                <span class="material-symbols-outlined text-3xl text-slate-300 mb-2">chat_bubble</span>
                <p class="text-sm text-slate-400">No conversations yet</p>
            </div>
        {:else}
            {#each $conversations as conv (conv.id)}
                {@const isActive = $activeConversationId === conv.id}
                <div class="group relative">
                    {#if renamingId === conv.id}
                        <div class="px-4 py-3 flex items-start gap-3">
                            <span class="material-symbols-outlined !text-[20px] text-slate-400 mt-0.5 shrink-0">chat_bubble</span>
                            <input
                                bind:this={renameInput}
                                bind:value={renameValue}
                                onblur={submitRename}
                                onkeydown={handleRenameKeydown}
                                class="flex-1 bg-slate-100 rounded-lg px-2 py-1 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-[#005a9a]/30 border border-slate-200"
                            />
                        </div>
                    {:else}
                        <button
                            onclick={() => handleSelectConversation(conv.id)}
                            class="w-full cursor-pointer px-4 py-3 pr-20 text-left flex items-start gap-3 transition-colors md:pr-4
                                   {isActive ? 'bg-[#F0F6FF]' : 'hover:bg-slate-50'}"
                        >
                            {#if isActive}
                                <div class="absolute left-0 top-0 bottom-0 w-1 bg-[#005a9a] rounded-r"></div>
                            {/if}
                            <span class="material-symbols-outlined !text-[20px] mt-0.5 shrink-0 {isActive ? 'text-[#005a9a]' : 'text-slate-400'}">chat_bubble</span>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm font-medium truncate {isActive ? 'text-slate-900' : 'text-slate-700'}">{conv.title}</p>
                            </div>
                        </button>
                        <!-- Hover Actions -->
                        <div class="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-0.5 rounded-lg border border-slate-100 bg-white/90 px-1 shadow-sm transition-opacity md:pointer-events-none md:opacity-0 md:group-hover:pointer-events-auto md:group-hover:opacity-100 md:group-focus-within:pointer-events-auto md:group-focus-within:opacity-100">
                            <button
                                onclick={() => startRename(conv.id, conv.title)}
                                class="rounded p-1.5 text-slate-400 hover:text-[#005a9a] hover:bg-slate-100 cursor-pointer transition-colors"
                                title="Rename"
                            >
                                <span class="material-symbols-outlined !text-[16px]">edit</span>
                            </button>
                            <button
                                onclick={() => handleDelete(conv.id)}
                                class="rounded p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 cursor-pointer transition-colors"
                                title="Delete"
                            >
                                <span class="material-symbols-outlined !text-[16px]">delete</span>
                            </button>
                        </div>
                    {/if}
                </div>
            {/each}
        {/if}
    </nav>

    <!-- User Profile Bottom -->
    <div class="border-t border-slate-200 p-3 shrink-0 sm:p-4">
        {#if $currentUser}
            <div class="rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
                <div class="flex items-center justify-between gap-3">
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="size-8 rounded-full bg-slate-200 flex items-center justify-center shrink-0">
                            <span class="material-symbols-outlined text-slate-500 !text-[18px]">person</span>
                        </div>
                        <div class="min-w-0">
                            <p class="truncate text-sm font-medium text-slate-700">{$currentUser.username}</p>
                            <p class="text-xs text-slate-400">Signed in</p>
                        </div>
                    </div>
                        <button
                            type="button"
                            onclick={() => void handleLogout()}
                            class="rounded-lg px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-white hover:text-slate-700"
                        >
                        Logout
                    </button>
                </div>

                <div class="mt-3 rounded-xl border border-slate-200 bg-white p-3">
                    <div class="flex items-center justify-between gap-3">
                        <div>
                            <p class="text-sm font-semibold text-slate-800">API Keys</p>
                        </div>
                        <button
                            type="button"
                            onclick={() => {
                                apiKeysModalOpen = true;
                                closeMobileSidebar();
                            }}
                            class="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-800"
                        >
                            <span class="material-symbols-outlined !text-[16px]">vpn_key</span>
                            Manage
                        </button>
                    </div>
                </div>
            </div>
        {:else}
            <div class="flex items-center gap-3 p-2 rounded-xl bg-slate-50 text-slate-500">
                <div class="size-8 rounded-full bg-slate-200 flex items-center justify-center">
                    <span class="material-symbols-outlined text-slate-500 !text-[18px]">person</span>
                </div>
                <span class="text-sm font-medium">Guest User</span>
            </div>
        {/if}
    </div>
</aside>

<ApiKeysModal open={apiKeysModalOpen} onclose={() => (apiKeysModalOpen = false)} />
