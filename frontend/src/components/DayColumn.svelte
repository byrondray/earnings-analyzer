<script>
  import { formatDate, isToday, formatReportTime } from '../lib/utils.js';
  import EarningsCard from './EarningsCard.svelte';

  let { dateStr, events, onShowAnalysis } = $props();

  let preMarket = $derived(events.filter(e => e.report_time === 'pre_market'));
  let postMarket = $derived(events.filter(e => e.report_time === 'post_market'));
  let unknown = $derived(events.filter(e => e.report_time === 'unknown'));
</script>

<div class="day-column" class:today={isToday(dateStr)}>
  <div class="day-header">
    <span class="day-name">{formatDate(dateStr)}</span>
    {#if events.length > 0}
      <span class="event-badge">{events.length}</span>
    {/if}
  </div>

  <div class="day-events">
    {#if preMarket.length > 0}
      <div class="time-section">
        <span class="time-label">🌅 Before Market</span>
        {#each preMarket as event}
          <EarningsCard {event} {onShowAnalysis} />
        {/each}
      </div>
    {/if}

    {#if postMarket.length > 0}
      <div class="time-section">
        <span class="time-label">🌙 After Market</span>
        {#each postMarket as event}
          <EarningsCard {event} {onShowAnalysis} />
        {/each}
      </div>
    {/if}

    {#if unknown.length > 0}
      <div class="time-section">
        <span class="time-label">⏰ TBD</span>
        {#each unknown as event}
          <EarningsCard {event} {onShowAnalysis} />
        {/each}
      </div>
    {/if}

    {#if events.length === 0}
      <div class="no-events">No earnings</div>
    {/if}
  </div>
</div>
