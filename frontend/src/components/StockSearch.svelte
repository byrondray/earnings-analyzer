<script>
  import { searchStock } from '../lib/api.js';
  import { formatLargeNumber } from '../lib/utils.js';

  let { onShowAnalysis } = $props();

  let query = $state('');
  let searching = $state(false);
  let results = $state(null);
  let error = $state(null);

  async function handleSearch(e) {
    e.preventDefault();
    const ticker = query.trim();
    if (!ticker) return;

    searching = true;
    error = null;
    results = null;

    try {
      const data = await searchStock(ticker);
      results = data;
    } catch (err) {
      error = err.message;
    } finally {
      searching = false;
    }
  }

  function clearSearch() {
    query = '';
    results = null;
    error = null;
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
        class="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
      />
      {#if query}
        <button type="button" onclick={clearSearch} class="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 bg-transparent border-none cursor-pointer text-sm p-1">✕</button>
      {/if}
    </div>
    <button
      type="submit"
      disabled={searching || !query.trim()}
      class="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-sm font-semibold px-5 py-2.5 rounded-lg border-none cursor-pointer transition-colors"
    >
      {#if searching}
        <span class="inline-block w-3.5 h-3.5 border-2 border-slate-400 border-t-white rounded-full animate-[spin_0.6s_linear_infinite]"></span>
      {:else}
        Search
      {/if}
    </button>
  </form>

  {#if error}
    <div class="mt-3 bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">
      ⚠️ {error}
    </div>
  {/if}

  {#if results}
    <div class="mt-3 bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
      <div class="flex justify-between items-center p-3 border-b border-slate-700">
        <h3 class="text-sm font-semibold text-slate-100">
          Results for <span class="text-blue-500">{results.ticker}</span>
        </h3>
        <button onclick={clearSearch} class="text-xs text-slate-400 hover:text-slate-200 bg-transparent border-none cursor-pointer">Clear</button>
      </div>

      {#if results.events.length === 0}
        <div class="p-4 text-sm text-slate-400 text-center">
          No upcoming earnings found for {results.ticker}
        </div>
      {:else}
        <div class="flex flex-col divide-y divide-slate-700">
          {#each results.events as event}
            <button
              class="flex items-center gap-4 p-3 text-left text-slate-100 bg-transparent border-none cursor-pointer hover:bg-slate-700/50 transition-colors font-[inherit]"
              onclick={() => {
                if (isInPast(event.report_date)) {
                  onShowAnalysis({ detail: { ticker: event.ticker, company_name: event.company_name } });
                }
              }}
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-bold text-sm text-blue-500">{event.ticker}</span>
                  <span class="text-xs text-slate-400 truncate">{event.company_name}</span>
                </div>
                <div class="flex items-center gap-3 mt-1 text-xs text-slate-400">
                  <span class="font-medium text-slate-300">{formatDateReadable(event.report_date)}</span>
                  <span>{formatTime(event.report_time)}</span>
                </div>
              </div>
              <div class="flex items-center gap-3 shrink-0 text-xs text-slate-400">
                {#if event.market_cap}
                  <span>Mkt Cap: {formatLargeNumber(event.market_cap)}</span>
                {/if}
                {#if event.eps_estimate != null}
                  <span>EPS Est: ${event.eps_estimate.toFixed(2)}</span>
                {/if}
                {#if isInPast(event.report_date)}
                  <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded bg-green-500/20 text-green-500 uppercase">Reported</span>
                {:else}
                  <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-500 uppercase">Upcoming</span>
                {/if}
              </div>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>
