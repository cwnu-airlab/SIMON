import { writable } from 'svelte/store';
import { browser } from '$app/environment';

const MARKDOWN_ENABLED_KEY = 'simon_markdown_enabled';

const initialValue = browser 
    ? localStorage.getItem(MARKDOWN_ENABLED_KEY) !== 'false' 
    : true;

export const markdownEnabled = writable<boolean>(initialValue);

if (browser) {
    markdownEnabled.subscribe((value) => {
        localStorage.setItem(MARKDOWN_ENABLED_KEY, String(value));
    });
}
