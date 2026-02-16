<script>
  import { formatLargeNumber } from '../lib/utils.js';
  import FavoriteButton from './FavoriteButton.svelte';
  import Sparkline from './Sparkline.svelte';

  let { event, onShowAnalysis, onError, user = null, isFavorited = false, onFavoriteChange } = $props();

  let hasReported = $derived(() => {
    const today = new Date().toISOString().split('T')[0];
    return event.report_date < today;
  });

  function handleClick() {
    onShowAnalysis({ detail: { ticker: event.ticker, company_name: event.company_name } });
  }
</script>

<button class="w-full bg-surface-primary/60 border border-border-subtle rounded-xl p-3 transition-all duration-200 text-left text-text-primary font-[inherit] cursor-pointer hover:bg-surface-elevated hover:border-accent-green/40 hover:shadow-[0_0_12px_rgba(52,172,86,0.1)]" onclick={handleClick}>
  <div class="flex justify-between items-center mb-1">
    <div class="flex items-center gap-1">
      <span class="font-bold text-sm text-accent-green">{event.ticker}</span>
      <FavoriteButton ticker={event.ticker} companyName={event.company_name} {isFavorited} {onFavoriteChange} {user} />
    </div>
    {#if !hasReported()}
      <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-md bg-accent-gold/15 text-accent-gold uppercase">Upcoming</span>
    {:else}
      <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-md bg-accent-green/15 text-accent-green uppercase">Reported</span>
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
  <Sparkline ticker={event.ticker} />
</button>
