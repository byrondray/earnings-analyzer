<script>
  import { triggerAnalysis, getAnalysis } from '../lib/api.js';
  import { formatLargeNumber } from '../lib/utils.js';
  import FavoriteButton from './FavoriteButton.svelte';

  let { event, onShowAnalysis, onError, user = null, isFavorited = false, onFavoriteChange } = $props();

  let analyzing = $state(false);
  let analysisResult = $state(null);
  let statusMessage = $state('');

  let hasReported = $derived(() => {
    const today = new Date().toISOString().split('T')[0];
    return event.report_date < today;
  });

  function computeQuarter(fiscalQuarter) {
    if (!fiscalQuarter) return 'Q4-2025';
    const monthMap = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
    const slashMatch = fiscalQuarter.match(/^([A-Za-z]+)\/([0-9]{4})$/);
    if (slashMatch) {
      const mon = monthMap[slashMatch[1].toLowerCase().slice(0, 3)];
      if (mon) return `Q${Math.ceil(mon / 3)}-${slashMatch[2]}`;
    }
    const d = new Date(fiscalQuarter + 'T00:00:00');
    if (isNaN(d.getTime())) return fiscalQuarter;
    return `Q${Math.ceil((d.getMonth() + 1) / 3)}-${d.getFullYear()}`;
  }

  async function handleClick() {
    if (analyzing) return;

    if (!hasReported()) {
      onError?.('Earnings not reported yet');
      return;
    }

    analyzing = true;
    statusMessage = 'Starting analysis...';

    try {
      let cached = await getAnalysis(event.ticker);
      if (cached) {
        analysisResult = cached;
        onShowAnalysis({ detail: { ...cached, company_name: event.company_name } });
        analyzing = false;
        statusMessage = '';
        return;
      }

      const quarter = computeQuarter(event.fiscal_quarter);

      const result = await triggerAnalysis(event.ticker, quarter, (msg) => {
        statusMessage = msg;
      });
      analysisResult = result;
      onShowAnalysis({ detail: { ...result, company_name: event.company_name } });
    } catch (e) {
      onError?.(e.message);
    } finally {
      analyzing = false;
      statusMessage = '';
    }
  }

  let hasBeat = $derived(analysisResult && analysisResult.has_reported !== false && analysisResult.eps_surprise_pct > 0);
  let hasMiss = $derived(analysisResult && analysisResult.has_reported !== false && analysisResult.eps_surprise_pct < 0);
</script>

<button class="w-full bg-surface-primary/60 border border-border-subtle rounded-xl p-3 transition-all duration-200 text-left text-text-primary font-[inherit] {hasReported() ? 'cursor-pointer hover:not-disabled:bg-surface-elevated hover:not-disabled:border-accent-green/40 hover:not-disabled:shadow-[0_0_12px_rgba(52,172,86,0.1)] disabled:opacity-70 disabled:cursor-wait' : 'cursor-default opacity-70'}" onclick={handleClick} disabled={analyzing}>
  <div class="flex justify-between items-center mb-1">
    <div class="flex items-center gap-1">
      <span class="font-bold text-sm text-accent-green">{event.ticker}</span>
      <FavoriteButton ticker={event.ticker} companyName={event.company_name} {isFavorited} {onFavoriteChange} {user} />
    </div>
    {#if analyzing}
      <span class="inline-block w-3.5 h-3.5 border-2 border-border-subtle border-t-accent-green rounded-full animate-[spin_0.6s_linear_infinite]"></span>
    {:else if !hasReported()}
      <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-md bg-accent-gold/15 text-accent-gold uppercase">Upcoming</span>
    {:else if hasBeat}
      <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-md bg-accent-green/15 text-accent-green uppercase">Beat</span>
    {:else if hasMiss}
      <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-md bg-red-500/15 text-red-400 uppercase">Miss</span>
    {/if}
  </div>
  <div class="text-xs text-text-muted truncate mb-0.5">{event.company_name}</div>
  {#if event.market_cap}
    <div class="text-xs text-text-muted">Mkt Cap: {formatLargeNumber(event.market_cap)}</div>
  {/if}
  {#if event.eps_estimate}
    <div class="text-xs text-text-muted">EPS Est: ${event.eps_estimate.toFixed(2)}</div>
  {/if}
  {#if event.revenue_estimate}
    <div class="text-xs text-text-muted">Rev Est: {formatLargeNumber(event.revenue_estimate)}</div>
  {/if}
  {#if analyzing && statusMessage}
    <div class="text-[0.65rem] text-accent-green/80 mt-1 animate-pulse">{statusMessage}</div>
  {/if}
</button>
