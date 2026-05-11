<script lang="ts">
  import { ApiError, attachmentRawUrl, createConversation, uploadAttachment } from "$lib/api";
  import {
    attachmentError,
    conversationAttachments,
    pendingMessageAttachments,
    uploadingAttachment,
  } from "$lib/stores/attachments";
  import { activeConversationId, conversations } from "$lib/stores/conversations";

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

  const PDF_MAX_BYTES = 50 * 1024 * 1024;
  const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
  const IMAGE_MIME_PREFIX = "image/";
  const ALLOWED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);

  let value = $state("");
  let fileInput: HTMLInputElement | null = $state(null);

  function isImageFile(file: File): boolean {
    if (file.type.startsWith(IMAGE_MIME_PREFIX)) return true;
    const lower = file.name.toLowerCase();
    return lower.endsWith(".png") || lower.endsWith(".jpg") || lower.endsWith(".jpeg") || lower.endsWith(".webp");
  }

  function isPdfFile(file: File): boolean {
    return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  }

  function sendMessage() {
    const trimmed = value.trim();
    if (isStreaming || disabled) return;
    if ($uploadingAttachment) {
      attachmentError.set("Wait for the attachment to finish uploading.");
      return;
    }
    if (!trimmed && $pendingMessageAttachments.length === 0) return;
    onSend?.(trimmed);
    value = "";
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  async function ensureConversation(): Promise<string | null> {
    let convId = $activeConversationId;
    if (convId) return convId;
    try {
      const created = await createConversation();
      convId = created.id;
      activeConversationId.set(created.id);
      conversations.update((list) => [created, ...list]);
      return convId;
    } catch (err) {
      attachmentError.set(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Failed to create conversation",
      );
      return null;
    }
  }

  async function handleFileSelected(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0];
    target.value = ""; // allow re-selecting the same filename
    if (!file) return;

    attachmentError.set(null);

    const isImage = isImageFile(file);
    const isPdf = isPdfFile(file);
    if (!isImage && !isPdf) {
      attachmentError.set("Only PDF or PNG/JPEG/WebP images are supported.");
      return;
    }
    if (isImage && !ALLOWED_IMAGE_TYPES.has(file.type)) {
      attachmentError.set(`Unsupported image type: ${file.type || "unknown"}`);
      return;
    }
    const limit = isImage ? IMAGE_MAX_BYTES : PDF_MAX_BYTES;
    if (file.size > limit) {
      const limitMb = Math.round(limit / 1024 / 1024);
      attachmentError.set(
        `File exceeds ${limitMb}MB limit (${(file.size / 1024 / 1024).toFixed(1)}MB).`,
      );
      return;
    }

    const convId = await ensureConversation();
    if (!convId) return;

    uploadingAttachment.set({ filename: file.name, progress: 0 });
    try {
      const meta = await uploadAttachment(convId, file, (loaded, total) => {
        uploadingAttachment.set({
          filename: file.name,
          progress: total > 0 ? loaded / total : 0,
        });
      });
      if (meta.attachment_type === "image") {
        pendingMessageAttachments.update((list) => [...list, meta]);
      } else {
        conversationAttachments.update((list) => [...list, meta]);
      }
    } catch (err) {
      attachmentError.set(
        err instanceof ApiError || err instanceof Error ? err.message : "Upload failed",
      );
    } finally {
      uploadingAttachment.set(null);
    }
  }

  function removePendingImage(id: number) {
    pendingMessageAttachments.update((list) => list.filter((a) => a.id !== id));
  }

  function openFilePicker() {
    fileInput?.click();
  }

  // Block accidental tab refresh/close while an upload is in flight. The
  // server-side OCR continues even on disconnect, so the row still lands in
  // the DB, but the user loses the in-progress UI state and may not realize
  // it. The native beforeunload prompt catches the common accidental case.
  $effect(() => {
    if (!$uploadingAttachment) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  });
</script>

<div class="shrink-0 bg-white px-3 pb-3 pt-0 sm:px-6 sm:pb-6">
  <div class="mx-auto w-full max-w-4xl">
    {#if $uploadingAttachment}
      <div class="mb-2 flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
        <span class="material-symbols-outlined !text-[16px] animate-pulse text-[#005a9a]">cloud_upload</span>
        <span class="truncate max-w-[14rem]" title={$uploadingAttachment.filename}>{$uploadingAttachment.filename}</span>
        <div class="flex-1 h-1.5 rounded-full bg-slate-200 overflow-hidden">
          <div
            class="h-full rounded-full bg-[#005a9a] transition-[width] duration-200"
            style="width: {Math.min(100, Math.round($uploadingAttachment.progress * 100))}%"
          ></div>
        </div>
        <span class="tabular-nums shrink-0">{$uploadingAttachment.progress < 1 ? `${Math.round($uploadingAttachment.progress * 100)}%` : "Processing…"}</span>
      </div>
    {/if}
    {#if $pendingMessageAttachments.length > 0}
      <div class="mb-2 flex flex-wrap gap-2">
        {#each $pendingMessageAttachments as att (att.id)}
          {#if $activeConversationId}
            <div class="relative inline-flex items-center overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <img
                src={attachmentRawUrl($activeConversationId, att.id)}
                alt={att.filename}
                class="block h-16 w-16 object-cover"
                loading="lazy"
              />
              <span class="px-2 text-xs text-slate-600 max-w-[10rem] truncate" title={att.filename}>{att.filename}</span>
              <button
                type="button"
                class="absolute top-0 right-0 m-0.5 rounded-full bg-white/90 p-0.5 text-slate-500 hover:text-red-600 cursor-pointer shadow"
                aria-label="Remove {att.filename}"
                onclick={() => removePendingImage(att.id)}
              >
                <span class="material-symbols-outlined !text-[14px]">close</span>
              </button>
            </div>
          {/if}
        {/each}
      </div>
    {/if}

    <div class="relative rounded-2xl border border-slate-200 bg-white shadow-sm transition-all focus-within:border-transparent focus-within:ring-2 focus-within:ring-[#005a9a]">
      <textarea
        bind:value
        class="min-h-[56px] max-h-32 w-full resize-none rounded-2xl border-0 bg-transparent py-3.5 pl-12 pr-14 text-[15px] text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-0 sm:py-4"
        placeholder={$uploadingAttachment ? `Uploading ${$uploadingAttachment.filename}…` : "Message SIMON..."}
        rows="1"
        onkeydown={onKeydown}
        disabled={isStreaming || disabled}
      ></textarea>

      <input
        type="file"
        accept="application/pdf,image/png,image/jpeg,image/webp"
        class="hidden"
        bind:this={fileInput}
        onchange={handleFileSelected}
      />
      <button
        type="button"
        class="absolute left-2 bottom-2 p-2 text-slate-500 rounded-xl hover:bg-slate-100 hover:text-[#005a9a] transition-colors disabled:opacity-50 cursor-pointer"
        onclick={openFilePicker}
        disabled={isStreaming || disabled || !!$uploadingAttachment}
        aria-label="Attach PDF or image"
        title="Attach PDF (max 50MB) or image (max 10MB)"
      >
        <span class="material-symbols-outlined !text-[20px]">attach_file</span>
      </button>

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
          disabled={(!value.trim() && $pendingMessageAttachments.length === 0) || disabled || !!$uploadingAttachment}
        >
          <span class="material-symbols-outlined !text-[20px]">send</span>
        </button>
      {/if}
    </div>
  </div>
  <p class="mt-2 px-2 text-center text-[11px] text-slate-400">SIMON can make mistakes. Consider verifying important information.</p>
</div>
