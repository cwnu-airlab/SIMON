<script lang="ts">
  import AuthPanel from "$lib/components/AuthPanel.svelte";
  import ChatWindow from "$lib/components/ChatWindow.svelte";
  import SettingsPanel from "$lib/components/SettingsPanel.svelte";
  import MarkdownToggle from "$lib/components/MarkdownToggle.svelte";
  import { authLoading, currentUser } from "$lib/stores/auth";
  import { activeConversation } from "$lib/stores/conversations";
  import { toggleMobileSidebar } from "$lib/stores/ui";

  let settingsOpen = $state(false);
</script>

<div class="relative flex h-full min-h-0 flex-col">
  <header class="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3 shrink-0 sm:px-6 sm:py-4">
    <div class="flex min-w-0 items-center gap-3">
      <button
        type="button"
        class="inline-flex rounded-xl border border-slate-200 p-2 text-slate-600 transition hover:bg-slate-50 hover:text-slate-900 lg:hidden"
        aria-label="Open navigation"
        onclick={toggleMobileSidebar}
      >
        <span class="material-symbols-outlined !text-[20px]">menu</span>
      </button>
      <h2 class="truncate text-base font-semibold text-slate-900 sm:text-lg">
        {$currentUser ? ($activeConversation?.title ?? 'New Chat') : 'Account Access'}
      </h2>
    </div>
    {#if $currentUser}
      <div class="flex shrink-0 items-center gap-2 sm:gap-4">
        <MarkdownToggle />
        <button
          onclick={() => (settingsOpen = !settingsOpen)}
          class="cursor-pointer rounded-xl p-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
          aria-label="Toggle settings"
        >
          <span class="material-symbols-outlined">settings</span>
        </button>
      </div>
    {/if}
  </header>

  <div class="min-h-0 flex-1 overflow-hidden">
    {#if $authLoading}
      <div class="flex h-full items-center justify-center text-sm text-slate-500">Loading account...</div>
    {:else if !$currentUser}
      <AuthPanel />
    {:else}
      <ChatWindow />
    {/if}
  </div>
</div>

{#if $currentUser}
  <SettingsPanel open={settingsOpen} onclose={() => (settingsOpen = false)} />
{/if}
