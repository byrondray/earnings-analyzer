<script>
  import { formatDate, isToday, formatReportTime } from '../lib/utils.js';
  import EarningsCard from './EarningsCard.svelte';

  let { dateStr, events, onShowAnalysis } = $props();

  let preMarket = $derived(events.filter(e => e.report_time === 'pre_market'));
  let postMarket = $derived(events.filter(e => e.report_time === 'post_market'));
  let unknown = $derived(events.filter(e => e.report_time === 'unknown'));
</script>

<div class="bg-slate-800 rounded-lg border min-h-50 flex flex-col {isToday(dateStr) ? 'border-blue-500 shadow-[0_0_0_1px_#3b82f6]' : 'border-slate-700'}">
  <div class="flex justify-between items-center p-3 border-b border-slate-700">
    <span class="font-semibold text-sm">{formatDate(dateStr)}</span>
    {#if events.length > 0}
      <span class="bg-blue-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">{events.length}</span>
    {/if}
  </div>

  <div class="p-2 flex-1 overflow-y-auto flex flex-col gap-2">
    {#if preMarket.length > 0}
      <div class="flex flex-col gap-1.5">
        <span class="text-xs text-slate-400 font-semibold uppercase tracking-wide py-1">🌅 Before Market</span>
        {#each preMarket as event}
          <EarningsCard {event} {onShowAnalysis} />
        {/each}
      </div>
    {/if}

    {#if postMarket.length > 0}
      <div class="flex flex-col gap-1.5">
        <span class="text-xs text-slate-400 font-semibold uppercase tracking-wide py-1">🌙 After Market</span>
        {#each postMarket as event}
          <EarningsCard {event} {onShowAnalysis} />
        {/each}
      </div>
    {/if}

    {#if unknown.length > 0}
      <div class="flex flex-col gap-1.5">
        <span class="text-xs text-slate-400 font-semibold uppercase tracking-wide py-1">⏰ TBD</span>
        {#each unknown as event}
          <EarningsCard {event} {onShowAnalysis} />
        {/each}
      </div>
    {/if}

    {#if events.length === 0}
      <div class="text-slate-400 text-sm text-center py-8">No earnings</div>
    {/if}
  </div>
</div>
