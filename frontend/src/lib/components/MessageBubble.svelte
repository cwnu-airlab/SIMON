<script lang="ts">
  import type { Message } from "$lib/api";
  import ThinkingCollapsible from "$lib/components/ThinkingCollapsible.svelte";
  import MarkdownRenderer from "$lib/components/MarkdownRenderer.svelte";
  import { markdownEnabled } from "$lib/stores/settings";

  let {
    message,
    showStreamingReasoning = false,
  }: {
    message: Message;
    showStreamingReasoning?: boolean;
  } = $props();

  let isUser = $derived(message.role === "user");
</script>

{#if isUser}
  <article class="mb-6 flex justify-end gap-2 sm:gap-3 items-end">
    <div class="flex max-w-[85%] flex-col gap-1 items-end sm:max-w-[70%] min-w-0">
      <span class="text-xs text-[var(--color-text-muted)] px-1">You</span>
      <div class="rounded-2xl rounded-tr-sm bg-[#005a9a] px-4 py-3 text-white shadow-sm sm:px-5 sm:py-3.5">
        <p class="text-[15px] leading-relaxed whitespace-pre-wrap">{message.content}</p>
      </div>
      <p class="text-[11px] text-[var(--color-text-muted)] px-1">
        {new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </p>
    </div>
    <div class="mb-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-slate-200 sm:size-8">
      <span class="material-symbols-outlined text-slate-500 !text-[18px]">person</span>
    </div>
  </article>
{:else}
  <article class="mb-6 flex items-start gap-2 sm:gap-3">
    <div class="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-[#005a9a] shadow-sm sm:size-8">
      <span class="material-symbols-outlined text-white !text-[18px]">smart_toy</span>
    </div>
    <div class="flex min-w-0 max-w-[88%] flex-col gap-2 sm:max-w-[80%]">
      <span class="text-xs text-[var(--color-text-muted)] px-1">SIMON</span>
      {#if message.reasoning}
        <ThinkingCollapsible reasoning={message.reasoning} isStreaming={showStreamingReasoning} />
      {/if}
      <div class="rounded-2xl rounded-tl-sm border border-blue-50 bg-[#F0F6FF] px-4 py-3 text-slate-800 shadow-sm sm:px-5 sm:py-3.5">
        <div class={`text-[15px] leading-relaxed ${$markdownEnabled ? '' : 'whitespace-pre-wrap'}`}>
          {#if $markdownEnabled}
            <MarkdownRenderer content={message.content} />
          {:else}
            {message.content}
          {/if}
        </div>
      </div>
      <p class="text-[11px] text-[var(--color-text-muted)] px-1">
        {new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </p>
    </div>
  </article>
{/if}
