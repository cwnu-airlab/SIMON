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
  <article class="mb-6 flex items-end gap-3 justify-end">
    <div class="flex flex-col gap-1 items-end max-w-[70%]">
      <span class="text-xs text-[var(--color-text-muted)] px-1">You</span>
      <div class="bg-[#104486] text-white px-5 py-3.5 rounded-2xl rounded-tr-sm shadow-sm">
        <p class="text-[15px] leading-relaxed whitespace-pre-wrap">{message.content}</p>
      </div>
      <p class="text-[11px] text-[var(--color-text-muted)] px-1">
        {new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </p>
    </div>
    <div class="size-8 rounded-full bg-slate-200 shrink-0 mb-1 flex items-center justify-center">
      <span class="material-symbols-outlined text-slate-500 !text-[18px]">person</span>
    </div>
  </article>
{:else}
  <article class="mb-6 flex items-start gap-3">
    <div class="size-8 rounded-full bg-[#104486] flex items-center justify-center shrink-0 mt-1 shadow-sm">
      <span class="material-symbols-outlined text-white !text-[18px]">smart_toy</span>
    </div>
    <div class="flex flex-col gap-2 max-w-[80%]">
      <span class="text-xs text-[var(--color-text-muted)] px-1">SIMON</span>
      {#if message.reasoning}
        <ThinkingCollapsible reasoning={message.reasoning} isStreaming={showStreamingReasoning} />
      {/if}
      <div class="bg-[#F0F6FF] text-slate-800 px-5 py-3.5 rounded-2xl rounded-tl-sm shadow-sm border border-blue-50">
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
