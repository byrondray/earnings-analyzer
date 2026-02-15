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

<section class="week-calendar">
  <nav class="week-nav">
    <button onclick={goPrevWeek} disabled={loading}>← Prev Week</button>
    <button class="today-btn" onclick={goToday} disabled={loading}>Today</button>
    <button onclick={goNextWeek} disabled={loading}>Next Week →</button>
  </nav>

  {#if weekData}
    <div class="week-header">
      <span class="week-range">
        {new Date(weekData.week_start + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}
        –
        {new Date(weekData.week_end + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
      </span>
      <span class="event-count">{weekData.events.length} earnings reports</span>
    </div>
  {/if}

  {#if loading}
    <div class="loading-grid">
      {#each Array(5) as _, i}
        <div class="skeleton-col"></div>
      {/each}
    </div>
  {:else if error}
    <div class="error-msg">
      <p>⚠️ {error}</p>
      <button onclick={() => loadWeek(currentDate)}>Retry</button>
    </div>
  {:else}
    <div class="day-grid">
      {#each days as day}
        <DayColumn dateStr={day} events={grouped[day] || []} {onShowAnalysis} />
      {/each}
    </div>
  {/if}
</section>
