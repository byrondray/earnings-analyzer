<script>
  import { addFavorite, removeFavorite } from '../lib/api.js';

  let { ticker, companyName = null, isFavorited = false, onFavoriteChange, user = null } = $props();

  let toggling = $state(false);

  async function toggle(e) {
    e.stopPropagation();
    e.preventDefault();
    if (toggling || !user) return;

    toggling = true;
    try {
      if (isFavorited) {
        await removeFavorite(ticker);
        onFavoriteChange?.(ticker, false);
      } else {
        await addFavorite(ticker, companyName);
        onFavoriteChange?.(ticker, true);
      }
    } catch {
      // silently fail — optimistic UI will revert on next fetch
    } finally {
      toggling = false;
    }
  }
</script>

{#if user}
  <button
    class="bg-transparent border-none p-0.5 cursor-pointer text-base leading-none transition-all duration-150 hover:scale-110 {toggling ? 'opacity-50 pointer-events-none' : ''}"
    onclick={toggle}
    title={isFavorited ? 'Remove from watchlist' : 'Add to watchlist'}
    aria-label={isFavorited ? `Remove ${ticker} from watchlist` : `Add ${ticker} to watchlist`}
  >
    {#if toggling}
      <span class="inline-block w-3.5 h-3.5 border-2 border-border-subtle border-t-accent-gold rounded-full animate-[spin_0.6s_linear_infinite]"></span>
    {:else if isFavorited}
      <span class="text-accent-gold">★</span>
    {:else}
      <span class="text-text-muted hover:text-accent-gold">☆</span>
    {/if}
  </button>
{/if}
