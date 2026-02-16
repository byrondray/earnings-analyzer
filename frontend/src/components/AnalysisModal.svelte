<script>
  import { formatLargeNumber, formatPercent } from '../lib/utils.js';

  let { data, onClose } = $props();

  function getSentimentColor(sentiment) {
    if (sentiment === 'bullish') return '#34AC56';
    if (sentiment === 'bearish') return '#ef4444';
    return '#f59e0b';
  }

  function getSentimentEmoji(sentiment) {
    if (sentiment === 'bullish') return '🟢';
    if (sentiment === 'bearish') return '🔴';
    return '🟡';
  }
</script>

<div class="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-1000 p-4" onclick={onClose} onkeydown={(e) => e.key === 'Escape' && onClose()} role="dialog" aria-modal="true" tabindex="-1">
  <div class="bg-surface-card rounded-3xl border border-border-subtle max-w-160 w-full max-h-[90vh] overflow-y-auto p-8 relative shadow-2xl" onclick={(e) => e.stopPropagation()} onkeydown={() => {}} role="presentation">
    <div class="absolute top-0 left-0 right-0 h-40 bg-linear-to-b from-accent-green/5 to-transparent rounded-t-3xl pointer-events-none"></div>

    <button class="absolute top-4 right-4 bg-transparent border-none text-text-muted text-2xl cursor-pointer p-1 leading-none hover:text-text-primary transition-colors" onclick={onClose}>✕</button>

    <header class="mb-6 relative">
      <h2 class="text-3xl font-extrabold text-accent-green tracking-tight">{data.ticker}</h2>
      {#if data.company_name}
        <p class="text-text-muted mt-1">{data.company_name}</p>
      {/if}
      {#if data.quarter}
        <span class="inline-block mt-2 px-3 py-1 bg-surface-primary border border-border-subtle rounded-xl text-sm text-text-muted">{data.quarter}</span>
      {/if}
    </header>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
      <div class="bg-surface-primary/80 rounded-2xl p-5 border border-border-subtle">
        <h3 class="text-xs text-accent-green font-bold mb-3 uppercase tracking-widest">EPS</h3>
        <table class="w-full border-collapse">
          <tbody>
            <tr>
              <td class="py-1.5 text-sm text-text-secondary">Estimate</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono text-text-primary">{data.eps_estimate != null ? `$${data.eps_estimate.toFixed(2)}` : 'N/A'}</td>
            </tr>
            {#if data.has_reported !== false}
            <tr>
              <td class="py-1.5 text-sm text-text-secondary">Actual</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono text-text-primary">{data.eps_actual != null ? `$${data.eps_actual.toFixed(2)}` : 'N/A'}</td>
            </tr>
            <tr>
              <td class="py-1.5 text-sm text-text-secondary">Surprise</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono {data.eps_surprise_pct > 0 ? 'text-accent-green' : data.eps_surprise_pct < 0 ? 'text-red-400' : 'text-text-primary'}">
                {data.eps_surprise_pct != null ? formatPercent(data.eps_surprise_pct) : 'N/A'}
              </td>
            </tr>
            {/if}
          </tbody>
        </table>
      </div>

      <div class="bg-surface-primary/80 rounded-2xl p-5 border border-border-subtle">
        <h3 class="text-xs text-accent-green font-bold mb-3 uppercase tracking-widest">Revenue</h3>
        <table class="w-full border-collapse">
          <tbody>
            <tr>
              <td class="py-1.5 text-sm text-text-secondary">Estimate</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono text-text-primary">{formatLargeNumber(data.revenue_estimate)}</td>
            </tr>
            {#if data.has_reported !== false}
            <tr>
              <td class="py-1.5 text-sm text-text-secondary">Actual</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono text-text-primary">{data.revenue_actual != null ? formatLargeNumber(data.revenue_actual) : 'N/A'}</td>
            </tr>
            <tr>
              <td class="py-1.5 text-sm text-text-secondary">Surprise</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono {data.revenue_surprise_pct > 0 ? 'text-accent-green' : data.revenue_surprise_pct < 0 ? 'text-red-400' : 'text-text-primary'}">
                {data.revenue_surprise_pct != null ? formatPercent(data.revenue_surprise_pct) : 'N/A'}
              </td>
            </tr>
            {/if}
          </tbody>
        </table>
      </div>
    </div>

    {#if data.has_reported === false}
      <div class="mb-5 bg-accent-gold/10 border border-accent-gold/30 rounded-2xl p-4">
        <p class="text-sm text-accent-gold">⏳ This company has not reported earnings yet. Estimates and sentiment are based on pre-report market expectations.</p>
      </div>
    {/if}

    <div class="mb-5">
      <h3 class="text-xs text-text-muted font-bold mb-2 uppercase tracking-widest">Guidance Summary</h3>
      <p class="text-sm leading-relaxed text-text-secondary">{data.guidance_summary || (data.has_reported === false ? 'Earnings not yet reported.' : 'No guidance data available.')}</p>
    </div>

    {#if data.financial_highlights || (data.raw_analysis && data.raw_analysis.financial_highlights)}
      {@const highlights = data.financial_highlights || data.raw_analysis?.financial_highlights}
      <div class="mb-5">
        <h3 class="text-xs text-text-muted font-bold mb-2 uppercase tracking-widest">Financial Highlights</h3>
        <div class="text-sm leading-relaxed text-text-secondary whitespace-pre-line bg-surface-primary/50 rounded-xl p-4 border border-border-subtle">{highlights}</div>
      </div>
    {/if}

    <div class="mb-5">
      <h3 class="text-xs text-text-muted font-bold mb-2 uppercase tracking-widest">Sentiment</h3>
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-2xl">{getSentimentEmoji(data.sentiment)}</span>
        <span class="font-bold text-lg" style="color: {getSentimentColor(data.sentiment)}">
          {data.sentiment?.toUpperCase() ?? 'N/A'}
        </span>
        {#if data.sentiment_score != null}
          <div class="w-30 h-1.5 bg-surface-primary rounded-full overflow-hidden">
            <div class="h-full rounded-full transition-[width] duration-300" style="width: {data.sentiment_score * 100}%; background: {getSentimentColor(data.sentiment)}"></div>
          </div>
          <span class="text-sm text-text-muted">{(data.sentiment_score * 100).toFixed(0)}% confidence</span>
        {/if}
      </div>
    </div>

    <div class="mb-5">
      <h3 class="text-xs text-text-muted font-bold mb-2 uppercase tracking-widest">Price Reaction</h3>
      {#if data.price_reaction_pct != null}
        <span class="text-2xl font-bold font-mono {data.price_reaction_pct > 0 ? 'text-accent-green' : data.price_reaction_pct < 0 ? 'text-red-400' : 'text-text-primary'}">
          {formatPercent(data.price_reaction_pct)}
        </span>
      {:else}
        <span class="text-sm text-text-muted">{data.has_reported === false ? 'Pending earnings report' : 'Not available'}</span>
      {/if}
    </div>

  </div>
</div>
