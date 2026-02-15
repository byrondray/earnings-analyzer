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

<button class="w-full bg-slate-900 border border-slate-700 rounded-md p-2.5 cursor-pointer transition-all text-left text-slate-100 font-[inherit] hover:not-disabled:bg-slate-700 hover:not-disabled:border-blue-500 disabled:opacity-70 disabled:cursor-wait" onclick={handleClick} disabled={analyzing}>
  <div class="flex justify-between items-center mb-1">
    <span class="font-bold text-sm text-blue-500">{event.ticker}</span>
    {#if analyzing}
      <span class="inline-block w-3.5 h-3.5 border-2 border-slate-700 border-t-blue-500 rounded-full animate-[spin_0.6s_linear_infinite]"></span>
    {:else if hasBeat}
      <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded bg-green-500/20 text-green-500 uppercase">Beat</span>
    {:else if hasMiss}
      <span class="text-[0.65rem] font-bold px-1.5 py-0.5 rounded bg-red-500/20 text-red-500 uppercase">Miss</span>
    {/if}
  </div>
  <div class="text-xs text-slate-400 truncate mb-0.5">{event.company_name}</div>
  {#if event.eps_estimate}
    <div class="text-xs text-slate-400">EPS Est: ${event.eps_estimate.toFixed(2)}</div>
  {/if}
  {#if event.revenue_estimate}
    <div class="text-xs text-slate-400">Rev Est: {formatLargeNumber(event.revenue_estimate)}</div>
  {/if}
  {#if error}
    <div class="text-[0.65rem] text-red-500 mt-1">⚠️ {error}</div>
  {/if}
</button>
