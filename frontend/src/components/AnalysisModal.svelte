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

<div class="modal-backdrop" onclick={onClose} role="dialog" aria-modal="true">
  <div class="modal-content" onclick={(e) => e.stopPropagation()}>
    <button class="close-btn" onclick={onClose}>✕</button>

    <header class="modal-header">
      <h2>{data.ticker}</h2>
      {#if data.company_name}
        <p class="company">{data.company_name}</p>
      {/if}
      {#if data.quarter}
        <span class="quarter-badge">{data.quarter}</span>
      {/if}
    </header>

    <div class="metrics-grid">
      <div class="metric-card">
        <h3>EPS</h3>
        <table>
          <tr>
            <td>Estimate</td>
            <td class="value">${data.eps_estimate?.toFixed(2) ?? 'N/A'}</td>
          </tr>
          <tr>
            <td>Actual</td>
            <td class="value">${data.eps_actual?.toFixed(2) ?? 'N/A'}</td>
          </tr>
          <tr>
            <td>Surprise</td>
            <td class="value" class:positive={data.eps_surprise_pct > 0} class:negative={data.eps_surprise_pct < 0}>
              {formatPercent(data.eps_surprise_pct)}
            </td>
          </tr>
        </table>
      </div>

      <div class="metric-card">
        <h3>Revenue</h3>
        <table>
          <tr>
            <td>Estimate</td>
            <td class="value">{formatLargeNumber(data.revenue_estimate)}</td>
          </tr>
          <tr>
            <td>Actual</td>
            <td class="value">{formatLargeNumber(data.revenue_actual)}</td>
          </tr>
          <tr>
            <td>Surprise</td>
            <td class="value" class:positive={data.revenue_surprise_pct > 0} class:negative={data.revenue_surprise_pct < 0}>
              {formatPercent(data.revenue_surprise_pct)}
            </td>
          </tr>
        </table>
      </div>
    </div>

    <div class="guidance-section">
      <h3>📋 Guidance Summary</h3>
      <p>{data.guidance_summary || 'No guidance data available.'}</p>
    </div>

    <div class="sentiment-section">
      <h3>Sentiment</h3>
      <div class="sentiment-display">
        <span class="sentiment-emoji">{getSentimentEmoji(data.sentiment)}</span>
        <span class="sentiment-label" style="color: {getSentimentColor(data.sentiment)}">
          {data.sentiment?.toUpperCase() ?? 'N/A'}
        </span>
        {#if data.sentiment_score != null}
          <div class="confidence-bar">
            <div class="confidence-fill" style="width: {data.sentiment_score * 100}%; background: {getSentimentColor(data.sentiment)}"></div>
          </div>
          <span class="confidence-label">{(data.sentiment_score * 100).toFixed(0)}% confidence</span>
        {/if}
      </div>
    </div>

    <div class="reaction-section">
      <h3>📈 Price Reaction</h3>
      <span class="price-reaction" class:positive={data.price_reaction_pct > 0} class:negative={data.price_reaction_pct < 0}>
        {formatPercent(data.price_reaction_pct)}
      </span>
    </div>

    {#if data.raw_analysis}
      <div class="raw-section">
        <button class="toggle-raw" onclick={() => showRaw = !showRaw}>
          {showRaw ? '▼' : '▶'} Raw Analysis Data
        </button>
        {#if showRaw}
          <pre class="raw-data">{JSON.stringify(data.raw_analysis, null, 2)}</pre>
        {/if}
      </div>
    {/if}
  </div>
</div>
