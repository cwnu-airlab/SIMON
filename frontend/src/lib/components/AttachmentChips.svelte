<script lang="ts">
  import { ApiError, deleteAttachment, type AttachmentMeta } from "$lib/api";
  import {
    attachmentError,
    conversationAttachments,
    uploadingAttachment,
  } from "$lib/stores/attachments";
  import { activeConversationId } from "$lib/stores/conversations";

  async function handleDelete(att: AttachmentMeta) {
    const conversationId = $activeConversationId;
    if (!conversationId) return;
    attachmentError.set(null);
    try {
      await deleteAttachment(conversationId, att.id);
      conversationAttachments.update((list) => list.filter((a) => a.id !== att.id));
    } catch (err) {
      attachmentError.set(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Failed to remove attachment",
      );
    }
  }
</script>

{#if $uploadingAttachment || $conversationAttachments.length > 0 || $attachmentError}
  <div class="mx-auto w-full max-w-4xl px-3 pb-1 pt-1 sm:px-6">
    {#if $attachmentError}
      <div class="mb-2 flex items-center justify-between gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-xs text-red-800">
        <span class="truncate">{$attachmentError}</span>
        <button
          type="button"
          class="cursor-pointer text-red-500 hover:text-red-700"
          aria-label="Dismiss attachment error"
          onclick={() => attachmentError.set(null)}
        >
          <span class="material-symbols-outlined !text-[16px]">close</span>
        </button>
      </div>
    {/if}

    <div class="flex flex-wrap gap-2">
      {#each $conversationAttachments as att (att.id)}
        <span class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 shadow-sm">
          <span class="material-symbols-outlined !text-[14px] text-[#005a9a]">picture_as_pdf</span>
          <span class="max-w-[180px] truncate" title={att.filename}>{att.filename}</span>
          {#if att.pages != null}
            <span class="text-slate-400">· {att.pages}p</span>
          {/if}
          <button
            type="button"
            class="ml-0.5 cursor-pointer text-slate-400 hover:text-red-600"
            aria-label="Remove {att.filename}"
            onclick={() => handleDelete(att)}
          >
            <span class="material-symbols-outlined !text-[14px]">close</span>
          </button>
        </span>
      {/each}

      {#if $uploadingAttachment}
        <span class="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs text-blue-800">
          <span class="material-symbols-outlined !text-[14px] animate-pulse">upload</span>
          <span class="max-w-[180px] truncate">{$uploadingAttachment.filename}</span>
          <span class="text-blue-500">{Math.round($uploadingAttachment.progress * 100)}%</span>
        </span>
      {/if}
    </div>
  </div>
{/if}
