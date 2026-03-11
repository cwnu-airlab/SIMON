<script lang="ts">
  let {
    reasoning,
    isStreaming = false,
  }: {
    reasoning: string;
    isStreaming?: boolean;
  } = $props();

  let expanded = $state(false);
</script>

{#if reasoning}
  <div class="w-fit">
    <button
      type="button"
      class="bg-slate-50 border border-slate-100 rounded-xl px-4 py-2 flex items-center gap-2 cursor-pointer hover:bg-slate-100 transition-colors"
      onclick={() => (expanded = !expanded)}
    >
      <span class={`material-symbols-outlined text-[var(--color-text-muted)] !text-[16px] ${isStreaming ? 'animate-pulse' : ''}`}>psychology</span>
      <span class="text-sm text-[var(--color-text-muted)] font-medium">
        {isStreaming ? 'Thinking...' : 'Thought process'}
      </span>
      <span class={`material-symbols-outlined text-[var(--color-text-muted)] !text-[16px] transition-transform ${expanded ? 'rotate-180' : ''}`}>expand_more</span>
    </button>
    {#if expanded}
      <pre class="mt-2 max-h-56 overflow-auto bg-slate-50 border border-slate-100 rounded-xl px-4 py-3 text-xs leading-relaxed text-[var(--color-text-muted)] whitespace-pre-wrap">{reasoning}</pre>
    {/if}
  </div>
{/if}
