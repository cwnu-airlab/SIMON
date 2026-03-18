<script lang="ts">
  import { authError, authLoading, login, signup } from "$lib/stores/auth";

  let mode = $state<"login" | "signup">("login");
  let username = $state("");
  let password = $state("");

  let title = $derived(mode === "login" ? "Sign in to SIMON" : "Create your SIMON account");
  let subtitle = $derived(
    mode === "login"
      ? "Access your own conversations and continue previous chats."
      : "Create a local account to keep your conversations private.",
  );

  async function handleSubmit(): Promise<void> {
    if (!username.trim() || !password) {
      return;
    }

    if (mode === "login") {
      await login(username.trim(), password);
      return;
    }

    await signup(username.trim(), password);
  }
</script>

<section class="flex h-full items-center justify-center p-4 sm:p-8">
  <div class="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/60 sm:rounded-3xl sm:p-8">
    <div class="mb-8 text-center">
      <div class="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-[#005a9a] text-[#9BC2F9] shadow-lg shadow-[#005a9a]/20 sm:size-16">
        <span class="material-symbols-outlined text-4xl" style="font-variation-settings: 'FILL' 1">forum</span>
      </div>
      <h1 class="text-2xl font-black text-slate-900 sm:text-3xl">{title}</h1>
      <p class="mt-2 text-sm leading-6 text-slate-500">{subtitle}</p>
    </div>

    <div class="mb-6 flex rounded-2xl bg-slate-100 p-1">
      <button
        type="button"
        class={`flex-1 rounded-xl px-4 py-2 text-sm font-semibold transition-colors ${mode === 'login' ? 'bg-white text-[#005a9a] shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
        onclick={() => (mode = "login")}
      >
        Login
      </button>
      <button
        type="button"
        class={`flex-1 rounded-xl px-4 py-2 text-sm font-semibold transition-colors ${mode === 'signup' ? 'bg-white text-[#005a9a] shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
        onclick={() => (mode = "signup")}
      >
        Sign Up
      </button>
    </div>

    <form class="space-y-4" onsubmit={(event) => {
      event.preventDefault();
      void handleSubmit();
    }}>
      <label class="block">
        <span class="mb-2 block text-sm font-medium text-slate-700">Username</span>
        <input
          bind:value={username}
          class="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-[#005a9a] focus:bg-white focus:ring-2 focus:ring-[#005a9a]/15"
          placeholder="your_name"
          autocomplete="username"
          minlength="3"
          maxlength="32"
        />
      </label>

      <label class="block">
        <span class="mb-2 block text-sm font-medium text-slate-700">Password</span>
        <input
          bind:value={password}
          type="password"
          class="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-[#005a9a] focus:bg-white focus:ring-2 focus:ring-[#005a9a]/15"
          placeholder="At least 8 characters"
          autocomplete={mode === "login" ? "current-password" : "new-password"}
          minlength="8"
          maxlength="128"
        />
      </label>

      {#if $authError}
        <div class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {$authError}
        </div>
      {/if}

      <button
        type="submit"
        disabled={$authLoading || !username.trim() || password.length < 8}
        class="flex w-full items-center justify-center rounded-2xl bg-[#005a9a] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#004a80] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {$authLoading ? "Please wait..." : mode === "login" ? "Login" : "Create Account"}
      </button>
    </form>
  </div>
</section>
