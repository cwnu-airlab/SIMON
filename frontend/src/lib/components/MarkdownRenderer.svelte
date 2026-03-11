<script lang="ts">
    import DOMPurify from 'isomorphic-dompurify';
    import { Marked } from 'marked';
    import markedKatex from 'marked-katex-extension';
    import { markedHighlight } from 'marked-highlight';
    import hljs from 'highlight.js';
    import 'highlight.js/styles/github-dark.css';
    import 'katex/dist/katex.min.css';

    let { content = '' }: { content?: string } = $props();

    const markdownParser = new Marked(
        markedKatex({
            throwOnError: false,
            nonStandard: true,
        }),
        markedHighlight({
            langPrefix: 'hljs language-',
            highlight(code, lang) {
                const language = hljs.getLanguage(lang) ? lang : 'plaintext';
                return hljs.highlight(code, { language }).value;
            }
        })
    );

    let htmlContent = $derived(
        DOMPurify.sanitize(markdownParser.parse(content) as string, {
            USE_PROFILES: {
                html: true,
                svg: true,
                mathMl: true,
            },
        })
    );
</script>

<div class="prose prose-sm prose-slate max-w-none markdown-body">
    {@html htmlContent}
</div>

<style>
    :global(.markdown-body) {
        --tw-prose-body: #1e293b;
        --tw-prose-headings: #0f172a;
        --tw-prose-links: #104486;
        --tw-prose-bold: #0f172a;
        --tw-prose-code: #104486;
        --tw-prose-quotes: #334155;
        --tw-prose-quote-borders: #9BC2F9;
    }

    :global(.markdown-body pre) {
        background-color: #1E293B;
        padding: 1rem;
        border-radius: 0.5rem;
        overflow-x: auto;
    }

    :global(.markdown-body code) {
        background-color: #E8F0FE;
        color: #104486;
        padding: 0.2rem 0.4rem;
        border-radius: 0.25rem;
        font-size: 0.875em;
    }

    :global(.markdown-body pre code) {
        background-color: transparent;
        color: inherit;
        padding: 0;
    }

    :global(.markdown-body .katex-display) {
        margin: 1rem 0;
        overflow-x: auto;
        overflow-y: hidden;
        padding-bottom: 0.25rem;
    }

    :global(.markdown-body .katex) {
        font-size: 1.05em;
    }
</style>
