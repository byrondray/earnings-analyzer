<script>
  import { getAnalysis, triggerAnalysis, fetchStockNews, fetchChartData } from '../lib/api.js';
  import { formatLargeNumber, formatPercent } from '../lib/utils.js';
  import FavoriteButton from './FavoriteButton.svelte';

  let { ticker, companyName = '', onBack, user = null, isFavorited = false, onFavoriteChange } = $props();

  let analysis = $state(null);
  let news = $state(null);
  let chartData = $state(null);
  let chartRange = $state('1M');
  let loadingAnalysis = $state(true);
  let loadingNews = $state(true);
  let loadingChart = $state(true);
  let analysisStatus = $state('');
  let analysisError = $state(null);

  const RANGES = ['1D', '5D', '1M', '3M', '6M', '1Y', '5Y'];

  $effect(() => {
    if (ticker) {
      loadAll();
    }
  });

  $effect(() => {
    loadChart(chartRange);
  });

  async function loadAll() {
    loadAnalysis();
    loadNews();
    loadChart(chartRange);
  }

  async function loadAnalysis() {
    loadingAnalysis = true;
    analysisError = null;
    analysisStatus = 'Checking for cached analysis...';
    try {
      let cached = await getAnalysis(ticker);
      if (cached) {
        analysis = cached;
        loadingAnalysis = false;
        analysisStatus = '';
        return;
      }
      analysisStatus = 'Starting analysis...';
      const result = await triggerAnalysis(ticker, guessQuarter(), (msg) => {
        analysisStatus = msg;
      });
      analysis = result;
    } catch (e) {
      analysisError = e.message;
    } finally {
      loadingAnalysis = false;
      analysisStatus = '';
    }
  }

  async function loadNews() {
    loadingNews = true;
    try {
      const data = await fetchStockNews(ticker);
      news = data.articles || [];
    } catch {
      news = [];
    } finally {
      loadingNews = false;
    }
  }

  async function loadChart(range) {
    loadingChart = true;
    try {
      chartData = await fetchChartData(ticker, range);
    } catch {
      chartData = { ticker, points: [], meta: {} };
    } finally {
      loadingChart = false;
    }
  }

  function guessQuarter() {
    const now = new Date();
    const q = Math.ceil((now.getMonth() + 1) / 3);
    return `Q${q}-${now.getFullYear()}`;
  }

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

  let allNA = $derived(analysis && analysis.eps_estimate == null && analysis.eps_actual == null && analysis.revenue_estimate == null && analysis.revenue_actual == null);

  let chartPath = $derived.by(() => {
    if (!chartData?.points?.length || chartData.points.length < 2) return '';
    const prices = chartData.points.map(p => p.c);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const w = 800;
    const h = 300;
    const pad = 8;
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

  let chartAreaPath = $derived.by(() => {
    if (!chartPath || !chartData?.points?.length) return '';
    const prices = chartData.points.map(p => p.c);
    const w = 800;
    const h = 300;
    return `${chartPath} L${w},${h} L0,${h} Z`;
  });

  let chartColor = $derived.by(() => {
    if (!chartData?.points?.length || chartData.points.length < 2) return '#34AC56';
    const first = chartData.points[0].c;
    const last = chartData.points[chartData.points.length - 1].c;
    return last >= first ? '#34AC56' : '#ef4444';
  });

  let priceChange = $derived.by(() => {
    if (!chartData?.points?.length || chartData.points.length < 2) return null;
    const first = chartData.points[0].c;
    const last = chartData.points[chartData.points.length - 1].c;
    const change = last - first;
    const pct = (change / first) * 100;
    return { change: change.toFixed(2), pct: pct.toFixed(2), positive: change >= 0 };
  });

  let currentPrice = $derived(chartData?.meta?.regularMarketPrice ?? chartData?.points?.[chartData.points.length - 1]?.c);

  let chartYLabels = $derived.by(() => {
    if (!chartData?.points?.length) return [];
    const prices = chartData.points.map(p => p.c);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const steps = 5;
    const labels = [];
    for (let i = 0; i <= steps; i++) {
      const value = min + (range * i) / steps;
      labels.push({ value: value.toFixed(2), y: ((300 - 16) - ((value - min) / range) * (300 - 16)).toFixed(1) });
    }
    return labels;
  });

  function formatNewsDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const diff = now - d;
    const hours = Math.floor(diff / 3600000);
    if (hours < 1) return 'Just now';
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
</script>

<div class="w-full animate-[fade-in-up_0.3s_ease-out]">
  <button
    class="mb-6 flex items-center gap-2 text-text-muted hover:text-accent-green bg-transparent border-none cursor-pointer text-sm font-medium transition-colors"
    onclick={onBack}
  >
    <span class="text-lg">←</span> Back
  </button>

  <header class="mb-8">
    <div class="flex items-center gap-3 mb-1">
      <h2 class="text-4xl font-extrabold text-accent-green tracking-tight">{ticker}</h2>
      <FavoriteButton {ticker} companyName={companyName || analysis?.company_name} {isFavorited} {onFavoriteChange} {user} />
    </div>
    {#if companyName || analysis?.company_name}
      <p class="text-text-muted text-lg">{companyName || analysis?.company_name}</p>
    {/if}
    {#if currentPrice}
      <div class="flex items-center gap-3 mt-2">
        <span class="text-3xl font-bold text-text-primary font-mono">${currentPrice.toFixed(2)}</span>
        {#if priceChange}
          <span class="text-lg font-semibold font-mono {priceChange.positive ? 'text-accent-green' : 'text-red-400'}">
            {priceChange.positive ? '+' : ''}{priceChange.change} ({priceChange.positive ? '+' : ''}{priceChange.pct}%)
          </span>
        {/if}
      </div>
    {/if}
    {#if analysis?.quarter}
      <span class="inline-block mt-2 px-3 py-1 bg-surface-primary border border-border-subtle rounded-xl text-sm text-text-muted">{analysis.quarter}</span>
    {/if}
  </header>

  <!-- Chart Section -->
  <section class="glass-card-solid rounded-2xl p-6 mb-6">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-sm font-bold text-text-muted uppercase tracking-widest">Price Chart</h3>
      <div class="flex gap-1">
        {#each RANGES as r}
          <button
            class="px-3 py-1.5 text-xs font-semibold rounded-lg border transition-all duration-150 cursor-pointer {chartRange === r ? 'bg-accent-green text-white border-accent-green' : 'bg-transparent text-text-muted border-border-subtle hover:border-accent-green/40 hover:text-text-secondary'}"
            onclick={() => chartRange = r}
          >
            {r}
          </button>
        {/each}
      </div>
    </div>

    {#if loadingChart}
      <div class="h-75 flex items-center justify-center">
        <div class="w-6 h-6 border-2 border-border-subtle border-t-accent-green rounded-full animate-spin"></div>
      </div>
    {:else if chartData?.points?.length > 1}
      <div class="relative">
        <svg viewBox="0 0 800 300" class="w-full h-75" preserveAspectRatio="none">
          <defs>
            <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color={chartColor} stop-opacity="0.25" />
              <stop offset="100%" stop-color={chartColor} stop-opacity="0" />
            </linearGradient>
          </defs>
          {#each chartYLabels as label}
            <line x1="0" y1={label.y} x2="800" y2={label.y} stroke="rgba(255,255,255,0.04)" stroke-width="1" />
          {/each}
          <path d={chartAreaPath} fill="url(#chartGrad)" />
          <path d={chartPath} fill="none" stroke={chartColor} stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
        </svg>
        <div class="absolute top-0 right-0 flex flex-col items-end gap-0.5 pointer-events-none">
          {#each chartYLabels as label}
            <span class="text-[0.6rem] text-text-muted font-mono" style="position:absolute; top:{label.y}px; transform:translateY(-50%)">${label.value}</span>
          {/each}
        </div>
      </div>
    {:else}
      <div class="h-75 flex items-center justify-center text-text-muted text-sm">No chart data available</div>
    {/if}
  </section>

  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <!-- Analysis Section (2/3 width) -->
    <div class="lg:col-span-2 flex flex-col gap-6">
      {#if loadingAnalysis}
        <div class="glass-card-solid rounded-2xl p-6">
          <div class="flex items-center gap-3">
            <div class="w-5 h-5 border-2 border-border-subtle border-t-accent-green rounded-full animate-spin"></div>
            <span class="text-sm text-text-muted">{analysisStatus || 'Loading analysis...'}</span>
          </div>
        </div>
      {:else if analysisError}
        <div class="glass-card-solid rounded-2xl p-6">
          <p class="text-red-400 text-sm">⚠️ {analysisError}</p>
          <button class="mt-3 px-4 py-2 bg-accent-green text-white border-none rounded-xl cursor-pointer text-sm font-semibold hover:brightness-110 transition-all" onclick={loadAnalysis}>Retry Analysis</button>
        </div>
      {:else if analysis}
        {#if allNA && analysis.has_reported !== false}
          <div class="bg-accent-gold/10 border border-accent-gold/30 rounded-2xl p-5">
            <p class="text-sm text-accent-gold font-semibold mb-1">Limited Data Available</p>
            <p class="text-sm text-text-muted">Insufficient public earnings data was found for this company.</p>
          </div>
        {/if}

        {#if !allNA}
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div class="glass-card-solid rounded-2xl p-5">
              <h3 class="text-xs text-accent-green font-bold mb-3 uppercase tracking-widest">EPS</h3>
              <table class="w-full border-collapse">
                <tbody>
                  <tr>
                    <td class="py-1.5 text-sm text-text-secondary">Estimate</td>
                    <td class="py-1.5 text-sm text-right font-semibold font-mono text-text-primary">{analysis.eps_estimate != null ? `$${analysis.eps_estimate.toFixed(2)}` : 'N/A'}</td>
                  </tr>
                  {#if analysis.has_reported !== false}
                  <tr>
                    <td class="py-1.5 text-sm text-text-secondary">Actual</td>
                    <td class="py-1.5 text-sm text-right font-semibold font-mono text-text-primary">{analysis.eps_actual != null ? `$${analysis.eps_actual.toFixed(2)}` : 'N/A'}</td>
                  </tr>
                  <tr>
                    <td class="py-1.5 text-sm text-text-secondary">Surprise</td>
                    <td class="py-1.5 text-sm text-right font-semibold font-mono {analysis.eps_surprise_pct > 0 ? 'text-accent-green' : analysis.eps_surprise_pct < 0 ? 'text-red-400' : 'text-text-primary'}">
                      {analysis.eps_surprise_pct != null ? formatPercent(analysis.eps_surprise_pct) : 'N/A'}
                    </td>
                  </tr>
                  {/if}
                </tbody>
              </table>
            </div>

            <div class="glass-card-solid rounded-2xl p-5">
              <h3 class="text-xs text-accent-green font-bold mb-3 uppercase tracking-widest">Revenue</h3>
              <table class="w-full border-collapse">
                <tbody>
                  <tr>
                    <td class="py-1.5 text-sm text-text-secondary">Estimate</td>
                    <td class="py-1.5 text-sm text-right font-semibold font-mono text-text-primary">{formatLargeNumber(analysis.revenue_estimate)}</td>
                  </tr>
                  {#if analysis.has_reported !== false}
                  <tr>
                    <td class="py-1.5 text-sm text-text-secondary">Actual</td>
                    <td class="py-1.5 text-sm text-right font-semibold font-mono text-text-primary">{analysis.revenue_actual != null ? formatLargeNumber(analysis.revenue_actual) : 'N/A'}</td>
                  </tr>
                  <tr>
                    <td class="py-1.5 text-sm text-text-secondary">Surprise</td>
                    <td class="py-1.5 text-sm text-right font-semibold font-mono {analysis.revenue_surprise_pct > 0 ? 'text-accent-green' : analysis.revenue_surprise_pct < 0 ? 'text-red-400' : 'text-text-primary'}">
                      {analysis.revenue_surprise_pct != null ? formatPercent(analysis.revenue_surprise_pct) : 'N/A'}
                    </td>
                  </tr>
                  {/if}
                </tbody>
              </table>
            </div>
          </div>
        {/if}

        {#if analysis.has_reported === false}
          <div class="bg-accent-gold/10 border border-accent-gold/30 rounded-2xl p-4">
            <p class="text-sm text-accent-gold">⏳ This company has not reported earnings yet. Estimates and sentiment are based on pre-report market expectations.</p>
          </div>
        {/if}

        <div class="glass-card-solid rounded-2xl p-5">
          <h3 class="text-xs text-text-muted font-bold mb-2 uppercase tracking-widest">Guidance Summary</h3>
          <p class="text-sm leading-relaxed text-text-secondary">{analysis.guidance_summary || (analysis.has_reported === false ? 'Earnings not yet reported.' : 'No guidance data available.')}</p>
        </div>

        {#if analysis.financial_highlights || (analysis.raw_analysis && analysis.raw_analysis.financial_highlights)}
          {@const highlights = analysis.financial_highlights || analysis.raw_analysis?.financial_highlights}
          <div class="glass-card-solid rounded-2xl p-5">
            <h3 class="text-xs text-text-muted font-bold mb-2 uppercase tracking-widest">Financial Highlights</h3>
            <div class="text-sm leading-relaxed text-text-secondary whitespace-pre-line">{highlights}</div>
          </div>
        {/if}

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="glass-card-solid rounded-2xl p-5">
            <h3 class="text-xs text-text-muted font-bold mb-2 uppercase tracking-widest">Sentiment</h3>
            <div class="flex items-center gap-3 flex-wrap">
              <span class="text-2xl">{getSentimentEmoji(analysis.sentiment)}</span>
              <span class="font-bold text-lg" style="color: {getSentimentColor(analysis.sentiment)}">
                {analysis.sentiment?.toUpperCase() ?? 'N/A'}
              </span>
              {#if analysis.sentiment_score != null}
                <div class="flex items-center gap-2 flex-1">
                  <div class="flex-1 h-1.5 bg-surface-primary rounded-full overflow-hidden">
                    <div class="h-full rounded-full transition-[width] duration-300" style="width: {analysis.sentiment_score * 100}%; background: {getSentimentColor(analysis.sentiment)}"></div>
                  </div>
                  <span class="text-sm text-text-muted">{(analysis.sentiment_score * 100).toFixed(0)}%</span>
                </div>
              {/if}
            </div>
          </div>

          <div class="glass-card-solid rounded-2xl p-5">
            <h3 class="text-xs text-text-muted font-bold mb-2 uppercase tracking-widest">Price Reaction</h3>
            {#if analysis.price_reaction_pct != null}
              <span class="text-2xl font-bold font-mono {analysis.price_reaction_pct > 0 ? 'text-accent-green' : analysis.price_reaction_pct < 0 ? 'text-red-400' : 'text-text-primary'}">
                {formatPercent(analysis.price_reaction_pct)}
              </span>
            {:else}
              <span class="text-sm text-text-muted">{analysis.has_reported === false ? 'Pending earnings report' : 'Not available'}</span>
            {/if}
          </div>
        </div>
      {/if}
    </div>

    <!-- News Section (1/3 width) -->
    <div class="flex flex-col gap-4">
      <div class="glass-card-solid rounded-2xl p-5">
        <h3 class="text-xs text-text-muted font-bold mb-4 uppercase tracking-widest">Latest News</h3>
        {#if loadingNews}
          <div class="flex flex-col gap-3">
            {#each Array(4) as _}
              <div class="h-20 bg-surface-primary rounded-xl animate-[pulse-skeleton_1.5s_ease-in-out_infinite]"></div>
            {/each}
          </div>
        {:else if news && news.length > 0}
          <div class="flex flex-col gap-3">
            {#each news as article}
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                class="group flex gap-3 p-3 rounded-xl hover:bg-surface-elevated/50 transition-all duration-150 no-underline"
              >
                {#if article.imageUrl}
                  <img
                    src={article.imageUrl}
                    alt=""
                    class="w-16 h-16 rounded-lg object-cover shrink-0 bg-surface-primary"
                    onerror={(e) => e.target.style.display = 'none'}
                  />
                {/if}
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-text-primary group-hover:text-accent-green transition-colors line-clamp-2 leading-snug">{article.title}</p>
                  <div class="flex items-center gap-2 mt-1.5">
                    <span class="text-xs text-text-muted">{article.source}</span>
                    <span class="text-xs text-text-muted">·</span>
                    <span class="text-xs text-text-muted">{formatNewsDate(article.publishedAt)}</span>
                  </div>
                </div>
              </a>
            {/each}
          </div>
        {:else}
          <p class="text-sm text-text-muted text-center py-4">No recent news found</p>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>
