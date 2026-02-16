<script>
  import { fetchWeekEarnings } from '../lib/api.js';
  import { getDaysOfWeek, groupByDate } from '../lib/utils.js';
  import DayColumn from './DayColumn.svelte';

  let { onShowAnalysis, onError } = $props();

  let weekData = $state(null);
  let loading = $state(true);
  let error = $state(null);

  function getDateFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get('week') || new Date().toISOString().split('T')[0];
  }

  let currentDate = $state(getDateFromUrl());

  function pushDate(dateStr) {
    const url = new URL(window.location.href);
    url.searchParams.set('week', dateStr);
    window.history.pushState({}, '', url);
    currentDate = dateStr;
  }

  async function loadWeek(dateStr) {
    loading = true;
    error = null;
    try {
      weekData = await fetchWeekEarnings(dateStr);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function goNextWeek() {
    if (!weekData) return;
    const next = new Date(weekData.week_end + 'T00:00:00');
    next.setDate(next.getDate() + 3);
    pushDate(next.toISOString().split('T')[0]);
  }

  function goPrevWeek() {
    if (!weekData) return;
    const prev = new Date(weekData.week_start + 'T00:00:00');
    prev.setDate(prev.getDate() - 3);
    pushDate(prev.toISOString().split('T')[0]);
  }

  function goToday() {
    pushDate(new Date().toISOString().split('T')[0]);
  }

  function handlePopState() {
    currentDate = getDateFromUrl();
  }

  $effect(() => {
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  });

  $effect(() => {
    loadWeek(currentDate);
  });

  let days = $derived(weekData ? getDaysOfWeek(weekData.week_start) : []);
  let grouped = $derived(weekData ? groupByDate(weekData.events) : {});
</script>

<section class="w-full">
  <nav class="flex justify-center gap-3 mb-5">
    <button class="px-5 py-2.5 bg-surface-card text-text-secondary border border-border-subtle rounded-2xl cursor-pointer text-sm transition-all duration-200 hover:not-disabled:bg-surface-elevated hover:not-disabled:border-accent-green/30 disabled:opacity-50 disabled:cursor-not-allowed" onclick={goPrevWeek} disabled={loading}>← Prev Week</button>
    <button class="px-5 py-2.5 bg-accent-green border border-accent-green rounded-2xl cursor-pointer text-sm font-bold text-white transition-all duration-200 hover:not-disabled:brightness-110 hover:not-disabled:shadow-[0_0_15px_rgba(52,172,86,0.3)] disabled:opacity-50 disabled:cursor-not-allowed" onclick={goToday} disabled={loading}>Today</button>
    <button class="px-5 py-2.5 bg-surface-card text-text-secondary border border-border-subtle rounded-2xl cursor-pointer text-sm transition-all duration-200 hover:not-disabled:bg-surface-elevated hover:not-disabled:border-accent-green/30 disabled:opacity-50 disabled:cursor-not-allowed" onclick={goNextWeek} disabled={loading}>Next Week →</button>
  </nav>

  {#if weekData}
    <div class="flex justify-between items-center mb-4 px-2">
      <span class="text-lg font-semibold text-text-primary">
        {new Date(weekData.week_start + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}
        –
        {new Date(weekData.week_end + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
      </span>
      <span class="text-text-muted text-sm">{weekData.events.length} earnings reports</span>
    </div>
  {/if}

  {#if loading}
    <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
      {#each Array(5) as _, i}
        <div class="bg-surface-card rounded-2xl h-75 animate-[pulse-skeleton_1.5s_ease-in-out_infinite] border border-border-subtle"></div>
      {/each}
    </div>
  {:else if error}
    <div class="text-center p-12 text-red-400">
      <p>⚠️ {error}</p>
      <button class="mt-4 px-5 py-2.5 bg-accent-green text-white border-none rounded-2xl cursor-pointer font-semibold transition-all duration-200 hover:brightness-110" onclick={() => loadWeek(currentDate)}>Retry</button>
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
      {#each days as day}
        <DayColumn dateStr={day} events={grouped[day] || []} {onShowAnalysis} {onError} />
      {/each}
    </div>
  {/if}
</section>
