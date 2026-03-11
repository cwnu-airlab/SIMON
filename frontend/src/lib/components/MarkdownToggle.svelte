<script lang="ts">
    import { markdownEnabled } from '$lib/stores/settings';
</script>

<label class="flex items-center cursor-pointer gap-2">
    <span class="text-sm text-[var(--color-text-muted)] font-medium">Markdown</span>
    <button
        type="button"
        onclick={() => ($markdownEnabled = !$markdownEnabled)}
        class="w-9 h-5 rounded-full relative focus:outline-none focus:ring-2 focus:ring-[#104486] focus:ring-offset-1 transition-colors {$markdownEnabled ? 'bg-[#104486]' : 'bg-slate-300'}"
        role="switch"
        aria-checked={$markdownEnabled}
        aria-label="Toggle markdown rendering"
    >
        <span class="absolute top-0.5 bg-white w-4 h-4 rounded-full shadow-sm transition-transform {$markdownEnabled ? 'right-0.5' : 'left-0.5'}"></span>
    </button>
</label>
