import { writable } from "svelte/store";

import type { AttachmentMeta } from "$lib/api";

export interface UploadState {
    filename: string;
    progress: number; // 0..1
}

// Conversation-scoped attachments (PDFs that survive every turn).
export const conversationAttachments = writable<AttachmentMeta[]>([]);
// Message-scoped images attached to the user message currently being composed.
// Cleared on send and on conversation switch.
export const pendingMessageAttachments = writable<AttachmentMeta[]>([]);
export const uploadingAttachment = writable<UploadState | null>(null);
export const attachmentError = writable<string | null>(null);

export function resetAttachments(): void {
    conversationAttachments.set([]);
    pendingMessageAttachments.set([]);
    uploadingAttachment.set(null);
    attachmentError.set(null);
}
