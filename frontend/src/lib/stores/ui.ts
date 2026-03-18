import { writable } from "svelte/store";

export const mobileSidebarOpen = writable(false);

export function openMobileSidebar(): void {
    mobileSidebarOpen.set(true);
}

export function closeMobileSidebar(): void {
    mobileSidebarOpen.set(false);
}

export function toggleMobileSidebar(): void {
    mobileSidebarOpen.update((open) => !open);
}
