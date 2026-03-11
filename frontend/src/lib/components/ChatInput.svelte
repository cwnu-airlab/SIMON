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

<div class="p-6 pt-0 bg-white shrink-0">
  <div class="relative max-w-4xl mx-auto shadow-sm rounded-2xl bg-white border border-slate-200 focus-within:ring-2 focus-within:ring-[#104486] focus-within:border-transparent transition-all">
    <textarea
      bind:value
      class="w-full bg-transparent border-0 rounded-2xl py-4 pl-4 pr-14 resize-none max-h-32 min-h-[56px] focus:ring-0 focus:outline-none text-slate-900 placeholder-slate-400 text-[15px]"
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
        class="absolute right-2 bottom-2 p-2 bg-[#104486] text-white rounded-xl hover:bg-[#0c3366] transition-colors disabled:opacity-50 flex items-center justify-center cursor-pointer"
        onclick={sendMessage}
        disabled={!value.trim() || disabled}
      >
        <span class="material-symbols-outlined !text-[20px]">send</span>
      </button>
    {/if}
  </div>
  <p class="text-center mt-2 text-[11px] text-slate-400">SIMON can make mistakes. Consider verifying important information.</p>
</div>
