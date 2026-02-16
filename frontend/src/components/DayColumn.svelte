<script>
  import { formatDate, isToday, formatReportTime } from '../lib/utils.js';
  import EarningsCard from './EarningsCard.svelte';

  let { dateStr, events, onShowAnalysis } = $props();

  let preMarket = $derived(events.filter(e => e.report_time === 'pre_market'));
  let postMarket = $derived(events.filter(e => e.report_time === 'post_market'));
  let unknown = $derived(events.filter(e => e.report_time === 'unknown'));
  let isPast = $derived(dateStr < new Date().toISOString().split('T')[0]);
  let allUnknownTime = $derived(preMarket.length === 0 && postMarket.length === 0);
</script>

<div class="glass-card-solid rounded-2xl min-h-50 flex flex-col {isToday(dateStr) ? 'glow-green-subtle border-accent-green!' : ''}">
  <div class="flex justify-between items-center p-3 border-b border-border-subtle">
    <span class="font-semibold text-sm text-text-secondary">{formatDate(dateStr)}</span>
    {#if events.length > 0}
      <span class="bg-accent-green/20 text-accent-green text-xs font-bold px-2.5 py-0.5 rounded-full">{events.length}</span>
    {/if}
  </div>

  <div class="p-2 flex-1 overflow-y-auto flex flex-col gap-2">
    {#if preMarket.length > 0}
      <div class="flex flex-col gap-1.5">
        <span class="text-xs text-text-muted font-semibold uppercase tracking-wide py-1">🌅 Before Market</span>
        {#each preMarket as event}
          <EarningsCard {event} {onShowAnalysis} />
        {/each}
      </div>
    {/if}

    {#if postMarket.length > 0}
      <div class="flex flex-col gap-1.5">
        <span class="text-xs text-text-muted font-semibold uppercase tracking-wide py-1">🌙 After Market</span>
        {#each postMarket as event}
          <EarningsCard {event} {onShowAnalysis} />
        {/each}
      </div>
    {/if}

    {#if unknown.length > 0}
      <div class="flex flex-col gap-1.5">
        {#if !allUnknownTime}
          <span class="text-xs text-text-muted font-semibold uppercase tracking-wide py-1">{isPast ? '📋 Reported' : '⏰ TBD'}</span>
        {/if}
        {#each unknown as event}
          <EarningsCard {event} {onShowAnalysis} />
        {/each}
      </div>
    {/if}

    {#if events.length === 0}
      <div class="text-text-muted text-sm text-center py-8">No earnings</div>
    {/if}
  </div>
</div>
