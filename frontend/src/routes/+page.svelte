<script lang="ts">
  import AuthPanel from "$lib/components/AuthPanel.svelte";
  import ChatWindow from "$lib/components/ChatWindow.svelte";
  import SettingsPanel from "$lib/components/SettingsPanel.svelte";
  import MarkdownToggle from "$lib/components/MarkdownToggle.svelte";
  import { authLoading, currentUser } from "$lib/stores/auth";
  import { activeConversation } from "$lib/stores/conversations";

  let settingsOpen = $state(false);
</script>

<div class="flex flex-col h-full relative">
  <header class="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-white shrink-0">
    <h2 class="text-lg font-semibold text-slate-900">
      {$currentUser ? ($activeConversation?.title ?? 'New Chat') : 'Account Access'}
    </h2>
    {#if $currentUser}
      <div class="flex items-center gap-4">
        <MarkdownToggle />
        <button
          onclick={() => (settingsOpen = !settingsOpen)}
          class="text-slate-500 hover:text-slate-700 transition-colors p-1 cursor-pointer"
          aria-label="Toggle settings"
        >
          <span class="material-symbols-outlined">settings</span>
        </button>
      </div>
    {/if}
  </header>

  <div class="flex-1 overflow-hidden">
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
