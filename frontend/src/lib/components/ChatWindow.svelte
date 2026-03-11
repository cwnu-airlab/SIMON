<script lang="ts">
  import { onMount, tick } from "svelte";
  import { get } from "svelte/store";

  import type { Message } from "$lib/api";
  import {
    ApiError,
    fetchConversation,
    fetchConversations,
    streamChatCompletion,
  } from "$lib/api";
  import ChatInput from "$lib/components/ChatInput.svelte";
  import MessageBubble from "$lib/components/MessageBubble.svelte";
  import ThinkingCollapsible from "$lib/components/ThinkingCollapsible.svelte";
  import MarkdownRenderer from "$lib/components/MarkdownRenderer.svelte";
  import { markdownEnabled } from "$lib/stores/settings";
  import { currentUser } from "$lib/stores/auth";
  import {
    chatError,
    isStreaming,
    messages,
    streamingContent,
    streamingReasoning,
  } from "$lib/stores/chat";
  import { activeConversationId, conversations } from "$lib/stores/conversations";

  let scroller: HTMLDivElement | null = $state(null);
  let abortController: AbortController | null = null;
  let lastLoadedConversationId: string | null = null;

  const suggestions = [
    { icon: "science", title: "Explain quantum computing", desc: "Complex concepts made simple" },
    { icon: "terminal", title: "Write a Python script", desc: "Automation and coding help" },
    { icon: "bug_report", title: "Debug my code", desc: "Solve issues fast" },
    { icon: "article", title: "Summarize this article", desc: "Key takeaways in seconds" },
  ];

  function toUiMessage(message: Message): Message {
    return {
      ...message,
      reasoning: message.reasoning ?? null,
    };
  }

  function normalizeError(error: unknown): string {
    if (error instanceof ApiError) {
      return error.message;
    }
    if (error instanceof Error) {
      return error.message;
    }
    return "Unexpected network error";
  }

  async function refreshConversations(): Promise<void> {
    if (!$currentUser) {
      conversations.set([]);
      activeConversationId.set(null);
      return;
    }

    const list = await fetchConversations();
    conversations.set(list);
    if (!get(activeConversationId) && list.length > 0) {
      activeConversationId.set(list[0].id);
    }
  }

  async function loadConversationMessages(conversationId: string | null): Promise<void> {
    if (!conversationId) {
      messages.set([]);
      lastLoadedConversationId = null;
      return;
    }

    try {
      const detail = await fetchConversation(conversationId);
      messages.set(detail.messages.map(toUiMessage));
      chatError.set(null);
      lastLoadedConversationId = conversationId;
    } catch (error) {
      chatError.set(normalizeError(error));
      messages.set([]);
    }
  }

  async function handleSend(message: string): Promise<void> {
    const userText = message.trim();
    if (!userText || get(isStreaming) || !$currentUser) {
      return;
    }

    const tempUserMessage: Message = {
      id: -Date.now(),
      conversation_id: get(activeConversationId) ?? "pending",
      role: "user",
      content: userText,
      reasoning: null,
      created_at: new Date().toISOString(),
    };

    messages.update((items) => [...items, tempUserMessage]);
    chatError.set(null);
    streamingReasoning.set("");
    streamingContent.set("");
    isStreaming.set(true);

    const localController = new AbortController();
    abortController = localController;

    let streamDone = false;
    let receivedConversationId = get(activeConversationId);
    let fullReasoning = "";
    let fullContent = "";

    try {
      await streamChatCompletion({
        message: userText,
        conversationId: get(activeConversationId) ?? undefined,
        signal: localController.signal,
        onStart: (conversationId: string) => {
          receivedConversationId = conversationId;
          activeConversationId.set(conversationId);
          messages.update((items) =>
            items.map((item) =>
              item.id === tempUserMessage.id ? { ...item, conversation_id: conversationId } : item,
            ),
          );
        },
        onReasoningDelta: (chunk: string) => {
          fullReasoning += chunk;
          streamingReasoning.update((current) => current + chunk);
        },
        onContentDelta: (chunk: string) => {
          fullContent += chunk;
          streamingContent.update((current) => current + chunk);
        },
        onDone: () => {
          streamDone = true;
        },
        onError: (message: string) => {
          chatError.set(message);
        },
      });

      if (streamDone && (fullReasoning || fullContent)) {
        const assistantMessage: Message = {
          id: -Date.now() - 1,
          conversation_id: receivedConversationId ?? get(activeConversationId) ?? "pending",
          role: "assistant",
          content: fullContent,
          reasoning: fullReasoning || null,
          created_at: new Date().toISOString(),
        };
        messages.update((items) => [...items, assistantMessage]);
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        chatError.set(normalizeError(error));
      }
    } finally {
      abortController = null;
      isStreaming.set(false);
      streamingReasoning.set("");
      streamingContent.set("");
      await refreshConversations();
      if (receivedConversationId && receivedConversationId !== lastLoadedConversationId) {
        await loadConversationMessages(receivedConversationId);
      }
    }
  }

  function handleStop(): void {
    abortController?.abort();
  }

  async function autoScroll(behavior: ScrollBehavior = "smooth"): Promise<void> {
    await tick();
    if (!scroller) {
      return;
    }
    scroller.scrollTo({
      top: scroller.scrollHeight,
      behavior,
    });
  }

  let showWelcome = $derived(!$activeConversationId && $messages.length === 0 && !$isStreaming);

  $effect(() => {
    if (!$currentUser) {
      messages.set([]);
      lastLoadedConversationId = null;
      return;
    }

    try {
      void refreshConversations().then(() => loadConversationMessages(get(activeConversationId)));
      void autoScroll("auto");
    } catch (error) {
      chatError.set(normalizeError(error));
    }
  });

  $effect(() => {
    if (!$currentUser) {
      return;
    }

    const convId = $activeConversationId;
    const streaming = $isStreaming;
    if (convId !== lastLoadedConversationId && !streaming) {
      void loadConversationMessages(convId);
    }
  });

  $effect(() => {
    void $messages;
    void $streamingReasoning;
    void $streamingContent;
    void autoScroll($isStreaming ? "auto" : "smooth");
  });
</script>

<section class="flex h-full flex-col bg-white">
  {#if $chatError}
    <div class="bg-[#FEF2F2] border-b border-[#FCA5A5] px-6 py-4 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-3 text-[#991B1B]">
        <span class="material-symbols-outlined text-xl">warning</span>
        <p class="text-sm font-bold">{$chatError}</p>
      </div>
      <button
        onclick={() => chatError.set(null)}
        class="bg-white text-[#991B1B] border border-[#FCA5A5] px-4 py-1.5 rounded text-sm font-semibold shadow-sm hover:bg-red-50 transition-colors cursor-pointer"
      >
        Dismiss
      </button>
    </div>
  {/if}

  {#if showWelcome}
    <div class="flex-1 overflow-y-auto flex flex-col items-center justify-center p-8">
      <div class="max-w-2xl w-full text-center mb-12">
        <div class="inline-flex items-center justify-center size-20 rounded-2xl bg-[#104486] text-[#9BC2F9] mb-6 shadow-xl shadow-[#104486]/20">
          <span class="material-symbols-outlined text-5xl" style="font-variation-settings: 'FILL' 1">forum</span>
        </div>
        <h2 class="text-4xl font-black text-slate-900 mb-3">Welcome to SIMON</h2>
        <p class="text-slate-500 text-lg">Start a new conversation to chat with AI</p>
      </div>
      <div class="max-w-3xl w-full grid grid-cols-2 gap-4">
        {#each suggestions as suggestion}
          <button
            onclick={() => handleSend(suggestion.title)}
            class="flex flex-col items-start text-left p-5 bg-white border border-[#9BC2F9]/30 rounded-xl hover:shadow-lg hover:border-[#9BC2F9] transition-all group cursor-pointer"
          >
            <span class="material-symbols-outlined text-[#104486] mb-3">{suggestion.icon}</span>
            <p class="text-slate-900 font-semibold mb-1 group-hover:text-[#104486] transition-colors">{suggestion.title}</p>
            <p class="text-slate-400 text-sm">{suggestion.desc}</p>
          </button>
        {/each}
      </div>
    </div>
  {:else}
    <div bind:this={scroller} class="flex-1 overflow-y-auto p-6">
      <div class="mx-auto max-w-4xl space-y-2">
        {#if $messages.length === 0 && $activeConversationId}
          <div class="flex flex-col items-center justify-center py-20 text-center">
            <span class="material-symbols-outlined text-4xl text-slate-300 mb-3">chat</span>
            <p class="text-slate-400">Send a message to start the conversation.</p>
          </div>
        {/if}

        {#each $messages as message (message.id)}
          <MessageBubble {message} />
        {/each}

        {#if $isStreaming && ($streamingReasoning || $streamingContent)}
          <article class="mb-6 flex items-start gap-3">
            <div class="size-8 rounded-full bg-[#104486] flex items-center justify-center shrink-0 mt-1 shadow-sm">
              <span class="material-symbols-outlined text-white !text-[18px]">smart_toy</span>
            </div>
            <div class="flex flex-col gap-2 max-w-[80%]">
              <div class="flex items-center gap-2">
                <span class="text-xs text-[var(--color-text-muted)] px-1">SIMON</span>
                {#if !$streamingContent}
                  <span class="text-[10px] text-slate-500 italic">Thinking...</span>
                {/if}
              </div>
              {#if $streamingReasoning}
                <ThinkingCollapsible reasoning={$streamingReasoning} isStreaming={true} />
              {/if}
              {#if $streamingContent}
                <div class={`bg-[#F0F6FF] text-slate-800 px-5 py-3.5 rounded-2xl rounded-tl-sm shadow-sm border border-blue-50 text-[15px] leading-relaxed ${$markdownEnabled ? '' : 'whitespace-pre-wrap'}`}>
                  {#if $markdownEnabled}
                    <MarkdownRenderer content={$streamingContent} />
                  {:else}
                    {$streamingContent}
                  {/if}
                </div>
              {/if}
            </div>
          </article>
        {/if}

        <div class="h-4"></div>
      </div>
    </div>
  {/if}

  <ChatInput
    isStreaming={$isStreaming}
    disabled={false}
    onSend={handleSend}
    onStop={handleStop}
  />
</section>
