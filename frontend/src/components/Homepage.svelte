<script>
  import { fetchHighlights } from '../lib/api.js';
  import { formatLargeNumber, formatDate } from '../lib/utils.js';

  let { onShowAnalysis, onNavigateToCalendar } = $props();

  let highlights = $state(null);
  let loading = $state(true);
  let error = $state(null);

  async function loadHighlights() {
    loading = true;
    error = null;
    try {
      highlights = await fetchHighlights();
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    loadHighlights();
  });

  function formatWeekRange(start, end) {
    const s = new Date(start + 'T00:00:00');
    const e = new Date(end + 'T00:00:00');
    return `${s.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })} – ${e.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`;
  }

  function hasReported(event) {
    const today = new Date().toISOString().split('T')[0];
    return event.report_date < today;
  }

  function handleCardClick(event) {
    onNavigateToCalendar(event.report_date);
  }
</script>

<section class="w-full">
  {#if loading}
    <div class="flex flex-col gap-8">
      {#each Array(2) as _}
        <div>
          <div class="h-6 w-60 bg-surface-card rounded-lg animate-[pulse-skeleton_1.5s_ease-in-out_infinite] mb-4"></div>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {#each Array(5) as _}
              <div class="bg-surface-card rounded-2xl h-44 animate-[pulse-skeleton_1.5s_ease-in-out_infinite] border border-border-subtle"></div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {:else if error}
    <div class="text-center p-12 text-red-400">
      <p>⚠️ {error}</p>
      <button class="mt-4 px-5 py-2.5 bg-accent-green text-white border-none rounded-2xl cursor-pointer font-semibold transition-all duration-200 hover:brightness-110" onclick={loadHighlights}>Retry</button>
    </div>
  {:else if highlights}
    <div class="flex flex-col gap-10">
      <!-- Last Week's Top Earnings -->
      <div>
        <div class="flex justify-between items-center mb-4 px-1">
          <div>
            <h2 class="text-lg font-bold text-text-primary">Last Week's Top Earnings</h2>
            <p class="text-text-muted text-xs mt-0.5">{formatWeekRange(highlights.last_week.week_start, highlights.last_week.week_end)}</p>
          </div>
          <button
            class="text-xs text-accent-green hover:text-accent-green/80 transition-colors cursor-pointer bg-transparent border-none font-semibold"
            onclick={() => onNavigateToCalendar(highlights.last_week.week_start)}
          >
            View full week →
          </button>
        </div>

        {#if highlights.last_week.events.length === 0}
          <div class="glass-card-solid rounded-2xl p-8 text-center text-text-muted text-sm">No earnings data available for last week</div>
        {:else}
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {#each highlights.last_week.events as event, i}
              <button
                class="glass-card-solid rounded-2xl p-4 text-left transition-all duration-200 cursor-pointer hover:bg-surface-elevated hover:border-accent-green/40 hover:shadow-[0_0_12px_rgba(52,172,86,0.1)] flex flex-col gap-1.5 {i === 0 ? 'glow-green sm:col-span-2 lg:col-span-1' : ''}"
                onclick={() => handleCardClick(event)}
              >
                {#if i === 0}
                  <span class="text-[0.6rem] font-bold uppercase tracking-wider text-accent-gold mb-0.5">🏆 Most Anticipated</span>
                {/if}
                <div class="flex justify-between items-center">
                  <span class="font-bold text-base text-accent-green">{event.ticker}</span>
                  <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-md bg-accent-green/15 text-accent-green uppercase">Reported</span>
                </div>
                <div class="text-xs text-text-muted truncate">{event.company_name}</div>
                <div class="text-xs text-text-muted">{formatDate(event.report_date)}</div>
                {#if event.market_cap}
                  <div class="text-xs text-text-muted">Mkt Cap: <span class="text-text-secondary font-medium">{formatLargeNumber(event.market_cap)}</span></div>
                {/if}
                {#if event.eps_estimate}
                  <div class="text-xs text-text-muted">EPS Est: <span class="text-text-secondary font-medium">${event.eps_estimate.toFixed(2)}</span></div>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <!-- This Week's Earnings to Watch -->
      <div>
        <div class="flex justify-between items-center mb-4 px-1">
          <div>
            <h2 class="text-lg font-bold text-text-primary">This Week to Watch</h2>
            <p class="text-text-muted text-xs mt-0.5">{formatWeekRange(highlights.this_week.week_start, highlights.this_week.week_end)}</p>
          </div>
          <button
            class="text-xs text-accent-green hover:text-accent-green/80 transition-colors cursor-pointer bg-transparent border-none font-semibold"
            onclick={() => onNavigateToCalendar(highlights.this_week.week_start)}
          >
            View full week →
          </button>
        </div>

        {#if highlights.this_week.events.length === 0}
          <div class="glass-card-solid rounded-2xl p-8 text-center text-text-muted text-sm">No earnings data available for this week</div>
        {:else}
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {#each highlights.this_week.events as event, i}
              <button
                class="glass-card-solid rounded-2xl p-4 text-left transition-all duration-200 flex flex-col gap-1.5 {hasReported(event) ? 'cursor-pointer hover:bg-surface-elevated hover:border-accent-green/40 hover:shadow-[0_0_12px_rgba(52,172,86,0.1)]' : 'cursor-default'} {i === 0 ? 'glow-green sm:col-span-2 lg:col-span-1' : ''}"
                onclick={() => handleCardClick(event)}
              >
                {#if i === 0}
                  <span class="text-[0.6rem] font-bold uppercase tracking-wider text-accent-gold mb-0.5">⭐ Most Anticipated</span>
                {/if}
                <div class="flex justify-between items-center">
                  <span class="font-bold text-base text-accent-green">{event.ticker}</span>
                  {#if hasReported(event)}
                    <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-md bg-accent-green/15 text-accent-green uppercase">Reported</span>
                  {:else}
                    <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-md bg-accent-gold/15 text-accent-gold uppercase">Upcoming</span>
                  {/if}
                </div>
                <div class="text-xs text-text-muted truncate">{event.company_name}</div>
                <div class="text-xs text-text-muted">{formatDate(event.report_date)}</div>
                {#if event.market_cap}
                  <div class="text-xs text-text-muted">Mkt Cap: <span class="text-text-secondary font-medium">{formatLargeNumber(event.market_cap)}</span></div>
                {/if}
                {#if event.eps_estimate}
                  <div class="text-xs text-text-muted">EPS Est: <span class="text-text-secondary font-medium">${event.eps_estimate.toFixed(2)}</span></div>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <div class="text-center mt-2">
        <button
          class="px-8 py-3 bg-accent-green border border-accent-green rounded-2xl cursor-pointer text-sm font-bold text-white transition-all duration-200 hover:brightness-110 hover:shadow-[0_0_15px_rgba(52,172,86,0.3)]"
          onclick={() => onNavigateToCalendar(new Date().toISOString().split('T')[0])}
        >
          View Full Calendar →
        </button>
      </div>
    </div>
  {/if}
</section>
