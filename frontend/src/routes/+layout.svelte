<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import { initializeAuth } from '$lib/stores/auth';
  import { closeMobileSidebar, mobileSidebarOpen } from '$lib/stores/ui';
  import type { Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();

  onMount(() => {
    void initializeAuth();
  });
</script>

<svelte:head>
  <title>SIMON</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&display=swap" rel="stylesheet" />
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
</svelte:head>

<div class="relative flex h-dvh overflow-hidden bg-[var(--color-bg-light)]">
  {#if $mobileSidebarOpen}
    <button
      type="button"
      class="fixed inset-0 z-30 bg-slate-950/35 lg:hidden"
      aria-label="Close navigation"
      onclick={closeMobileSidebar}
    ></button>
  {/if}

  <div
    class="sidebar-drawer fixed inset-y-0 left-0 z-40 w-[min(85vw,320px)]"
    style:transform={$mobileSidebarOpen ? 'translateX(0)' : 'translateX(-100%)'}
    style:transition="transform 200ms ease-out"
  >
    <Sidebar />
  </div>

  <main class="flex min-w-0 flex-1 flex-col bg-[var(--color-bg-light)]">
    {@render children()}
  </main>
</div>
