<script>
  let { message, onDismiss } = $props();

  $effect(() => {
    const timer = setTimeout(onDismiss, 6000);
    return () => clearTimeout(timer);
  });
</script>

<div class="fixed bottom-6 left-1/2 -translate-x-1/2 z-1100 max-w-120 w-[calc(100%-3rem)] animate-[fade-in-up_0.3s_ease-out]">
  <div class="bg-red-950/90 border border-red-500/40 rounded-2xl px-5 py-4 shadow-[0_0_30px_rgba(239,68,68,0.15)] backdrop-blur-sm flex items-start gap-3">
    <span class="text-red-400 text-lg shrink-0 mt-0.5">⚠️</span>
    <p class="text-sm text-red-200 flex-1">{message}</p>
    <button class="text-red-400/60 hover:text-red-300 transition-colors bg-transparent border-none cursor-pointer text-lg leading-none shrink-0 p-0.5" onclick={onDismiss}>✕</button>
  </div>
</div>
