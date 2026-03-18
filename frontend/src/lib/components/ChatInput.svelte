<script lang="ts">
  let {
    isStreaming = false,
    disabled = false,
    onSend,
    onStop,
  }: {
    isStreaming?: boolean;
    disabled?: boolean;
    onSend?: (message: string) => void;
    onStop?: () => void;
  } = $props();

  let value = $state("");

  function sendMessage() {
    const trimmed = value.trim();
    if (!trimmed || isStreaming || disabled) {
      return;
    }
    onSend?.(trimmed);
    value = "";
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }
</script>

<div class="shrink-0 bg-white px-3 pb-3 pt-0 sm:px-6 sm:pb-6">
  <div class="relative mx-auto w-full max-w-4xl rounded-2xl border border-slate-200 bg-white shadow-sm transition-all focus-within:border-transparent focus-within:ring-2 focus-within:ring-[#005a9a]">
    <textarea
      bind:value
      class="min-h-[56px] max-h-32 w-full resize-none rounded-2xl border-0 bg-transparent py-3.5 pl-4 pr-14 text-[15px] text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-0 sm:py-4"
      placeholder="Message SIMON..."
      rows="1"
      onkeydown={onKeydown}
      disabled={isStreaming || disabled}
    ></textarea>
    {#if isStreaming}
      <button
        type="button"
        class="absolute right-2 bottom-2 p-2 bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors flex items-center justify-center cursor-pointer"
        onclick={() => onStop?.()}
      >
        <span class="material-symbols-outlined !text-[20px]">stop</span>
      </button>
    {:else}
      <button
        type="button"
        class="absolute right-2 bottom-2 p-2 bg-[#005a9a] text-white rounded-xl hover:bg-[#004a80] transition-colors disabled:opacity-50 flex items-center justify-center cursor-pointer"
        onclick={sendMessage}
        disabled={!value.trim() || disabled}
      >
        <span class="material-symbols-outlined !text-[20px]">send</span>
      </button>
    {/if}
  </div>
  <p class="mt-2 px-2 text-center text-[11px] text-slate-400">SIMON can make mistakes. Consider verifying important information.</p>
</div>
