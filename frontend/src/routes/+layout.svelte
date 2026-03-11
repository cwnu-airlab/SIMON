<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import { initializeAuth } from '$lib/stores/auth';
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

<div class="flex h-screen overflow-hidden">
  <Sidebar />
  <main class="flex-1 min-w-0 bg-[var(--color-bg-light)]">
    {@render children()}
  </main>
</div>
