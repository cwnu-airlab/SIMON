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

<section class="flex h-full min-h-0 flex-col bg-white">
  {#if $chatError}
    <div class="flex shrink-0 flex-col gap-3 border-b border-[#FCA5A5] bg-[#FEF2F2] px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
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
    <div class="flex flex-1 flex-col items-center justify-center overflow-y-auto p-6 sm:p-8">
      <div class="mb-10 w-full max-w-2xl text-center sm:mb-12">
        <div class="mb-5 inline-flex size-16 items-center justify-center rounded-2xl bg-[#005a9a] text-[#9BC2F9] shadow-xl shadow-[#005a9a]/20 sm:mb-6 sm:size-20">
          <span class="material-symbols-outlined text-5xl" style="font-variation-settings: 'FILL' 1">forum</span>
        </div>
        <h2 class="mb-3 text-3xl font-black text-slate-900 sm:text-4xl">Welcome to SIMON</h2>
        <p class="text-base text-slate-500 sm:text-lg">Start a new conversation to chat with AI</p>
      </div>
      <div class="grid w-full max-w-3xl grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
        {#each suggestions as suggestion}
          <button
            onclick={() => handleSend(suggestion.title)}
            class="group flex cursor-pointer flex-col items-start rounded-xl border border-[#9BC2F9]/30 bg-white p-4 text-left transition-all hover:border-[#9BC2F9] hover:shadow-lg sm:p-5"
          >
            <span class="material-symbols-outlined text-[#005a9a] mb-3">{suggestion.icon}</span>
            <p class="text-slate-900 font-semibold mb-1 group-hover:text-[#005a9a] transition-colors">{suggestion.title}</p>
            <p class="text-slate-400 text-sm">{suggestion.desc}</p>
          </button>
        {/each}
      </div>
    </div>
  {:else}
    <div bind:this={scroller} class="flex-1 overflow-y-auto p-4 sm:p-6">
      <div class="mx-auto w-full max-w-4xl space-y-2">
        {#if $messages.length === 0 && $activeConversationId}
          <div class="flex flex-col items-center justify-center py-16 text-center sm:py-20">
            <span class="material-symbols-outlined text-4xl text-slate-300 mb-3">chat</span>
            <p class="text-slate-400">Send a message to start the conversation.</p>
          </div>
        {/if}

        {#each $messages as message (message.id)}
          <MessageBubble {message} />
        {/each}

        {#if $isStreaming && ($streamingReasoning || $streamingContent)}
          <article class="mb-6 flex items-start gap-2 sm:gap-3">
            <div class="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-[#005a9a] shadow-sm sm:size-8">
              <span class="material-symbols-outlined text-white !text-[18px]">smart_toy</span>
            </div>
            <div class="flex min-w-0 max-w-[88%] flex-col gap-2 sm:max-w-[80%]">
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
                <div class={`rounded-2xl rounded-tl-sm border border-blue-50 bg-[#F0F6FF] px-4 py-3 text-[15px] leading-relaxed text-slate-800 shadow-sm sm:px-5 sm:py-3.5 ${$markdownEnabled ? '' : 'whitespace-pre-wrap'}`}>
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
