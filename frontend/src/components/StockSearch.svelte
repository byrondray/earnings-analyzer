<script>
  import { searchStock } from '../lib/api.js';
  import { formatLargeNumber } from '../lib/utils.js';

  let { onShowAnalysis, onError } = $props();

  let query = $state('');
  let searching = $state(false);
  let results = $state(null);

  async function handleSearch(e) {
    e.preventDefault();
    const ticker = query.trim();
    if (!ticker) return;

    searching = true;
    results = null;

    try {
      const data = await searchStock(ticker);
      results = data;
    } catch (err) {
      if (onError) onError(err.message);
    } finally {
      searching = false;
    }
  }

  function clearSearch() {
    query = '';
    results = null;
  }

  function formatDateReadable(dateStr) {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  function formatTime(time) {
    if (time === 'pre_market') return '🌅 Before Market';
    if (time === 'post_market') return '🌙 After Market';
    return '⏰ TBD';
  }

  function isInPast(dateStr) {
    const today = new Date().toISOString().split('T')[0];
    return dateStr < today;
  }
</script>

<div class="mb-6">
  <form class="flex gap-2" onsubmit={handleSearch}>
    <div class="relative flex-1">
      <input
        type="text"
        bind:value={query}
        placeholder="Search stock ticker (e.g. AAPL, MSFT)"
        class="w-full bg-surface-input border border-border-subtle rounded-2xl px-4 py-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-green focus:ring-1 focus:ring-accent-green/50 transition-all duration-200"
      />
      {#if query}
        <button type="button" onclick={clearSearch} class="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary bg-transparent border-none cursor-pointer text-sm p-1 transition-colors">✕</button>
      {/if}
    </div>
    <button
      type="submit"
      disabled={searching || !query.trim()}
      class="bg-accent-green hover:brightness-110 hover:shadow-[0_0_15px_rgba(52,172,86,0.3)] disabled:bg-surface-card disabled:cursor-not-allowed text-white text-sm font-bold px-6 py-3 rounded-2xl border-none cursor-pointer transition-all duration-200"
    >
      {#if searching}
        <span class="inline-block w-3.5 h-3.5 border-2 border-accent-green/40 border-t-white rounded-full animate-[spin_0.6s_linear_infinite]"></span>
      {:else}
        Search
      {/if}
    </button>
  </form>



  {#if results}
    <div class="mt-3 glass-card-solid rounded-2xl overflow-hidden">
      <div class="flex justify-between items-center p-3 border-b border-border-subtle">
        <h3 class="text-sm font-semibold text-text-primary">
          Results for <span class="text-accent-green">{results.ticker}</span>
        </h3>
        <button onclick={clearSearch} class="text-xs text-text-muted hover:text-text-primary bg-transparent border-none cursor-pointer transition-colors">Clear</button>
      </div>

      {#if results.events.length === 0}
        <div class="p-4 text-sm text-text-muted text-center">
          No upcoming earnings found for {results.ticker}
        </div>
      {:else}
        <div class="flex flex-col divide-y divide-border-subtle">
          {#each results.events as event}
            <button
              class="flex items-center gap-4 p-3 text-left text-text-primary bg-transparent border-none cursor-pointer hover:bg-surface-elevated/50 transition-all duration-200 font-[inherit]"
              onclick={() => {
                if (isInPast(event.report_date)) {
                  onShowAnalysis({ detail: { ticker: event.ticker, company_name: event.company_name } });
                }
              }}
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-bold text-sm text-accent-green">{event.ticker}</span>
                  <span class="text-xs text-text-muted truncate">{event.company_name}</span>
                </div>
                <div class="flex items-center gap-3 mt-1 text-xs text-text-muted">
                  <span class="font-medium text-text-secondary">{formatDateReadable(event.report_date)}</span>
                  <span>{formatTime(event.report_time)}</span>
                </div>
              </div>
              <div class="flex items-center gap-3 shrink-0 text-xs text-text-muted">
                {#if event.market_cap}
                  <span>Mkt Cap: {formatLargeNumber(event.market_cap)}</span>
                {/if}
                {#if event.eps_estimate != null}
                  <span>EPS Est: ${event.eps_estimate.toFixed(2)}</span>
                {/if}
                {#if isInPast(event.report_date)}
                  <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-md bg-accent-green/15 text-accent-green uppercase">Reported</span>
                {:else}
                  <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-md bg-accent-gold/15 text-accent-gold uppercase">Upcoming</span>
                {/if}
              </div>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>
