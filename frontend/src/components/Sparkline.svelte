<script module>
  import { fetchSparklines } from '../lib/api.js';

  const sparklineCache = new Map();
  let pendingTickers = new Set();
  let pendingCallbacks = new Map();
  let batchTimer = null;

  function requestSparkline(ticker, callback) {
    const cached = sparklineCache.get(ticker);
    if (cached) {
      callback(cached);
      return;
    }

    if (!pendingCallbacks.has(ticker)) {
      pendingCallbacks.set(ticker, []);
    }
    pendingCallbacks.get(ticker).push(callback);
    pendingTickers.add(ticker);

    if (batchTimer) clearTimeout(batchTimer);
    batchTimer = setTimeout(flushBatch, 50);
  }

  async function flushBatch() {
    const tickers = [...pendingTickers];
    const callbacks = new Map(pendingCallbacks);
    pendingTickers.clear();
    pendingCallbacks.clear();
    batchTimer = null;

    if (!tickers.length) return;

    const CHUNK_SIZE = 10;
    for (let i = 0; i < tickers.length; i += CHUNK_SIZE) {
      const chunk = tickers.slice(i, i + CHUNK_SIZE);
      const data = await fetchSparklines(chunk);
      for (const [ticker, prices] of Object.entries(data)) {
        if (prices?.length) {
          sparklineCache.set(ticker, prices);
        }
        const cbs = callbacks.get(ticker) || [];
        cbs.forEach((cb) => cb(prices || []));
      }
      for (const ticker of chunk) {
        if (!data[ticker]) {
          const cbs = callbacks.get(ticker) || [];
          cbs.forEach((cb) => cb([]));
        }
      }
    }
  }
</script>

<script>
  let { ticker } = $props();

  let prices = $state([]);
  let visible = $state(false);
  let container = $state(null);

  $effect(() => {
    if (!container) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          visible = true;
          observer.disconnect();
        }
      },
      { rootMargin: '100px' }
    );
    observer.observe(container);
    return () => observer.disconnect();
  });

  $effect(() => {
    if (!ticker || !visible) return;
    requestSparkline(ticker, (data) => {
      prices = data;
    });
  });

  let path = $derived.by(() => {
    if (prices.length < 2) return '';
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const w = 100;
    const h = 32;
    const pad = 1;
    const usableH = h - pad * 2;
    const step = w / (prices.length - 1);

    return prices
      .map((p, i) => {
        const x = (i * step).toFixed(1);
        const y = (pad + usableH - ((p - min) / range) * usableH).toFixed(1);
        return `${i === 0 ? 'M' : 'L'}${x},${y}`;
      })
      .join(' ');
  });

  let areaPath = $derived.by(() => {
    if (!path) return '';
    return `${path} L100,32 L0,32 Z`;
  });

  let isUp = $derived(prices.length >= 2 && prices[prices.length - 1] >= prices[0]);
  let color = $derived(isUp ? 'var(--color-accent-green)' : '#ef4444');
</script>

<div bind:this={container} class="w-full mt-auto">
  {#if path}
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" class="w-full h-8">
      <defs>
        <linearGradient id="sparkFill-{ticker}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color={color} stop-opacity="0.25" />
          <stop offset="100%" stop-color={color} stop-opacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#sparkFill-{ticker})" />
      <path d={path} fill="none" stroke={color} stroke-width="1.5" vector-effect="non-scaling-stroke" />
    </svg>
  {/if}
</div>
