<script>
  import { formatLargeNumber, formatPercent } from '../lib/utils.js';

  let { data, onClose } = $props();
  let showRaw = $state(false);

  function getSentimentColor(sentiment) {
    if (sentiment === 'bullish') return '#22c55e';
    if (sentiment === 'bearish') return '#ef4444';
    return '#f59e0b';
  }

  function getSentimentEmoji(sentiment) {
    if (sentiment === 'bullish') return '🟢';
    if (sentiment === 'bearish') return '🔴';
    return '🟡';
  }
</script>

<div class="fixed inset-0 bg-black/70 flex items-center justify-center z-1000 p-4" onclick={onClose} onkeydown={(e) => e.key === 'Escape' && onClose()} role="dialog" aria-modal="true" tabindex="-1">
  <div class="bg-slate-800 rounded-xl border border-slate-700 max-w-160 w-full max-h-[90vh] overflow-y-auto p-8 relative" onclick={(e) => e.stopPropagation()} onkeydown={() => {}} role="presentation">
    <button class="absolute top-4 right-4 bg-transparent border-none text-slate-400 text-2xl cursor-pointer p-1 leading-none hover:text-slate-100" onclick={onClose}>✕</button>

    <header class="mb-6">
      <h2 class="text-3xl font-bold text-blue-500">{data.ticker}</h2>
      {#if data.company_name}
        <p class="text-slate-400 mt-1">{data.company_name}</p>
      {/if}
      {#if data.quarter}
        <span class="inline-block mt-2 px-2.5 py-1 bg-slate-900 rounded text-sm text-slate-400">{data.quarter}</span>
      {/if}
    </header>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
      <div class="bg-slate-900 rounded-lg p-4">
        <h3 class="text-sm text-slate-400 mb-3 uppercase tracking-wide">EPS</h3>
        <table class="w-full border-collapse">
          <tbody>
            <tr>
              <td class="py-1.5 text-sm">Estimate</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono">${data.eps_estimate?.toFixed(2) ?? 'N/A'}</td>
            </tr>
            <tr>
              <td class="py-1.5 text-sm">Actual</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono">${data.eps_actual?.toFixed(2) ?? 'N/A'}</td>
            </tr>
            <tr>
              <td class="py-1.5 text-sm">Surprise</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono {data.eps_surprise_pct > 0 ? 'text-green-500' : data.eps_surprise_pct < 0 ? 'text-red-500' : ''}">
                {formatPercent(data.eps_surprise_pct)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="bg-slate-900 rounded-lg p-4">
        <h3 class="text-sm text-slate-400 mb-3 uppercase tracking-wide">Revenue</h3>
        <table class="w-full border-collapse">
          <tbody>
            <tr>
              <td class="py-1.5 text-sm">Estimate</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono">{formatLargeNumber(data.revenue_estimate)}</td>
            </tr>
            <tr>
              <td class="py-1.5 text-sm">Actual</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono">{formatLargeNumber(data.revenue_actual)}</td>
            </tr>
            <tr>
              <td class="py-1.5 text-sm">Surprise</td>
              <td class="py-1.5 text-sm text-right font-semibold font-mono {data.revenue_surprise_pct > 0 ? 'text-green-500' : data.revenue_surprise_pct < 0 ? 'text-red-500' : ''}">
                {formatPercent(data.revenue_surprise_pct)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="mb-5">
      <h3 class="text-sm text-slate-400 mb-2 uppercase tracking-wide">📋 Guidance Summary</h3>
      <p class="text-sm leading-relaxed text-slate-100">{data.guidance_summary || 'No guidance data available.'}</p>
    </div>

    <div class="mb-5">
      <h3 class="text-sm text-slate-400 mb-2 uppercase tracking-wide">Sentiment</h3>
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-2xl">{getSentimentEmoji(data.sentiment)}</span>
        <span class="font-bold text-lg" style="color: {getSentimentColor(data.sentiment)}">
          {data.sentiment?.toUpperCase() ?? 'N/A'}
        </span>
        {#if data.sentiment_score != null}
          <div class="w-30 h-1.5 bg-slate-900 rounded-sm overflow-hidden">
            <div class="h-full rounded-sm transition-[width] duration-300" style="width: {data.sentiment_score * 100}%; background: {getSentimentColor(data.sentiment)}"></div>
          </div>
          <span class="text-sm text-slate-400">{(data.sentiment_score * 100).toFixed(0)}% confidence</span>
        {/if}
      </div>
    </div>

    <div class="mb-5">
      <h3 class="text-sm text-slate-400 mb-2 uppercase tracking-wide">📈 Price Reaction</h3>
      <span class="text-2xl font-bold font-mono {data.price_reaction_pct > 0 ? 'text-green-500' : data.price_reaction_pct < 0 ? 'text-red-500' : ''}">
        {formatPercent(data.price_reaction_pct)}
      </span>
    </div>

    {#if data.raw_analysis}
      <div class="mb-5">
        <button class="bg-transparent border-none text-slate-400 cursor-pointer text-sm py-1 font-[inherit] hover:text-slate-100" onclick={() => showRaw = !showRaw}>
          {showRaw ? '▼' : '▶'} Raw Analysis Data
        </button>
        {#if showRaw}
          <pre class="bg-slate-900 rounded-lg p-4 text-xs overflow-x-auto mt-2 text-slate-400 font-mono">{JSON.stringify(data.raw_analysis, null, 2)}</pre>
        {/if}
      </div>
    {/if}
  </div>
</div>
