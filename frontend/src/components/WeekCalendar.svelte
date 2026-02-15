<script>
  import { fetchWeekEarnings } from '../lib/api.js';
  import { getDaysOfWeek, groupByDate } from '../lib/utils.js';
  import DayColumn from './DayColumn.svelte';

  let { onShowAnalysis } = $props();

  let weekData = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let currentDate = $state(new Date().toISOString().split('T')[0]);

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
    currentDate = next.toISOString().split('T')[0];
    loadWeek(currentDate);
  }

  function goPrevWeek() {
    if (!weekData) return;
    const prev = new Date(weekData.week_start + 'T00:00:00');
    prev.setDate(prev.getDate() - 3);
    currentDate = prev.toISOString().split('T')[0];
    loadWeek(currentDate);
  }

  function goToday() {
    currentDate = new Date().toISOString().split('T')[0];
    loadWeek(currentDate);
  }

  $effect(() => {
    loadWeek(currentDate);
  });

  let days = $derived(weekData ? getDaysOfWeek(weekData.week_start) : []);
  let grouped = $derived(weekData ? groupByDate(weekData.events) : {});
</script>

<section class="w-full">
  <nav class="flex justify-center gap-3 mb-4">
    <button class="px-5 py-2 bg-slate-800 text-slate-100 border border-slate-700 rounded-lg cursor-pointer text-sm transition-colors hover:not-disabled:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed" onclick={goPrevWeek} disabled={loading}>← Prev Week</button>
    <button class="px-5 py-2 bg-blue-500 border border-blue-500 rounded-lg cursor-pointer text-sm font-semibold text-white transition-colors hover:not-disabled:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed" onclick={goToday} disabled={loading}>Today</button>
    <button class="px-5 py-2 bg-slate-800 text-slate-100 border border-slate-700 rounded-lg cursor-pointer text-sm transition-colors hover:not-disabled:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed" onclick={goNextWeek} disabled={loading}>Next Week →</button>
  </nav>

  {#if weekData}
    <div class="flex justify-between items-center mb-4 px-2">
      <span class="text-lg font-semibold">
        {new Date(weekData.week_start + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}
        –
        {new Date(weekData.week_end + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
      </span>
      <span class="text-slate-400 text-sm">{weekData.events.length} earnings reports</span>
    </div>
  {/if}

  {#if loading}
    <div class="grid grid-cols-1 md:grid-cols-5 gap-3">
      {#each Array(5) as _, i}
        <div class="bg-slate-800 rounded-lg h-75 animate-[pulse-skeleton_1.5s_ease-in-out_infinite]"></div>
      {/each}
    </div>
  {:else if error}
    <div class="text-center p-12 text-red-500">
      <p>⚠️ {error}</p>
      <button class="mt-4 px-4 py-2 bg-blue-500 text-white border-none rounded-lg cursor-pointer" onclick={() => loadWeek(currentDate)}>Retry</button>
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-5 gap-3">
      {#each days as day}
        <DayColumn dateStr={day} events={grouped[day] || []} {onShowAnalysis} />
      {/each}
    </div>
  {/if}
</section>
