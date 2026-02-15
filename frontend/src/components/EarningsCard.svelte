<script>
  import { triggerAnalysis, getAnalysis } from '../lib/api.js';
  import { formatLargeNumber } from '../lib/utils.js';

  let { event, onShowAnalysis } = $props();

  let analyzing = $state(false);
  let analysisResult = $state(null);
  let error = $state(null);

  async function handleClick() {
    if (analyzing) return;

    analyzing = true;
    error = null;

    try {
      let cached = await getAnalysis(event.ticker);
      if (cached) {
        analysisResult = cached;
        onShowAnalysis({ detail: { ...cached, company_name: event.company_name } });
        analyzing = false;
        return;
      }

      const quarter = event.fiscal_quarter
        ? `Q${Math.ceil(new Date(event.fiscal_quarter + 'T00:00:00').getMonth() / 3)}-${new Date(event.fiscal_quarter + 'T00:00:00').getFullYear()}`
        : 'Q4-2025';

      const result = await triggerAnalysis(event.ticker, quarter);
      analysisResult = result;
      onShowAnalysis({ detail: { ...result, company_name: event.company_name } });
    } catch (e) {
      error = e.message;
    } finally {
      analyzing = false;
    }
  }

  let hasBeat = $derived(analysisResult && analysisResult.eps_surprise_pct > 0);
  let hasMiss = $derived(analysisResult && analysisResult.eps_surprise_pct < 0);
</script>

<button class="earnings-card" onclick={handleClick} disabled={analyzing}>
  <div class="card-top">
    <span class="ticker">{event.ticker}</span>
    {#if analyzing}
      <span class="spinner"></span>
    {:else if hasBeat}
      <span class="badge beat">Beat</span>
    {:else if hasMiss}
      <span class="badge miss">Miss</span>
    {/if}
  </div>
  <div class="company-name">{event.company_name}</div>
  {#if event.eps_estimate}
    <div class="estimate">EPS Est: ${event.eps_estimate.toFixed(2)}</div>
  {/if}
  {#if event.revenue_estimate}
    <div class="estimate">Rev Est: {formatLargeNumber(event.revenue_estimate)}</div>
  {/if}
  {#if error}
    <div class="card-error">⚠️ {error}</div>
  {/if}
</button>
