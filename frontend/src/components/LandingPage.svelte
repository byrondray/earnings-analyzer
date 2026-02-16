<script>
  import { signIn } from '../lib/clerk.js';
</script>

<div class="min-h-screen text-text-primary font-sans radial-gradient-bg flex flex-col">
  <!-- Nav -->
  <nav class="max-w-350 w-full mx-auto px-6 py-5 flex justify-between items-center">
    <div class="flex items-center gap-2">
      <span class="text-xl font-extrabold tracking-tight">
        <span class="text-accent-green">Earnings</span> Analyzer
      </span>
    </div>
    <button
      class="px-5 py-2 text-sm font-semibold bg-accent-green border-none rounded-xl text-white cursor-pointer transition-all hover:brightness-110 hover:shadow-[0_0_15px_rgba(52,172,86,0.3)]"
      onclick={signIn}
    >Sign in</button>
  </nav>

  <!-- Hero -->
  <section class="flex-1 flex flex-col items-center justify-center px-6 pb-20">
    <div class="max-w-2xl text-center">
      <div class="inline-flex items-center gap-2 px-4 py-1.5 bg-accent-green/10 border border-accent-green/20 rounded-full mb-8">
        <span class="w-2 h-2 bg-accent-green rounded-full animate-pulse"></span>
        <span class="text-xs font-semibold text-accent-green uppercase tracking-wider">Live earnings data</span>
      </div>

      <h1 class="text-5xl sm:text-6xl font-extrabold tracking-tight leading-tight mb-6">
        AI-Powered<br/>
        <span class="text-accent-green">Earnings Analysis</span><br/>
        in Seconds
      </h1>

      <p class="text-text-muted text-lg leading-relaxed mb-10 max-w-xl mx-auto">
        Track upcoming earnings reports, get instant AI analysis of results,
        and build a watchlist of stocks you care about — all in one place.
      </p>

      <div class="flex flex-col sm:flex-row gap-4 justify-center mb-16">
        <button
          class="px-8 py-3.5 text-base font-bold bg-accent-green border-none rounded-2xl text-white cursor-pointer transition-all hover:brightness-110 hover:shadow-[0_0_20px_rgba(52,172,86,0.4)]"
          onclick={signIn}
        >Get Started — It's Free</button>
        <a
          href="#features"
          class="px-8 py-3.5 text-base font-semibold bg-surface-card border border-border-subtle rounded-2xl text-text-secondary cursor-pointer transition-all hover:bg-surface-elevated hover:border-accent-green/30 no-underline text-center"
        >See How It Works</a>
      </div>

      <!-- Preview mockup -->
      <div class="glass-card-solid rounded-2xl p-1 max-w-lg mx-auto">
        <div class="bg-surface-primary rounded-xl p-4">
          <div class="flex gap-3 mb-3">
            <div class="flex-1 bg-surface-card rounded-lg p-3 border border-border-subtle">
              <div class="text-accent-green font-bold text-sm mb-1">AAPL</div>
              <div class="text-xs text-text-muted">Apple Inc.</div>
              <div class="text-xs text-accent-green mt-1">▲ Beat EPS by 4.2%</div>
            </div>
            <div class="flex-1 bg-surface-card rounded-lg p-3 border border-border-subtle">
              <div class="text-accent-green font-bold text-sm mb-1">NVDA</div>
              <div class="text-xs text-text-muted">NVIDIA Corp.</div>
              <div class="text-xs text-accent-green mt-1">▲ Beat Rev by 8.1%</div>
            </div>
            <div class="flex-1 bg-surface-card rounded-lg p-3 border border-border-subtle">
              <div class="text-accent-green font-bold text-sm mb-1">MSFT</div>
              <div class="text-xs text-text-muted">Microsoft Corp.</div>
              <div class="text-xs text-accent-gold mt-1">⏳ Upcoming</div>
            </div>
          </div>
          <div class="bg-surface-card rounded-lg p-3 border border-border-subtle">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-accent-green font-bold text-sm">AI Analysis</span>
              <span class="text-[0.6rem] px-1.5 py-0.5 bg-accent-green/15 text-accent-green rounded-md font-bold">LIVE</span>
            </div>
            <div class="h-2 bg-accent-green/20 rounded-full overflow-hidden">
              <div class="h-full bg-accent-green rounded-full w-3/4 animate-pulse"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Features -->
  <section id="features" class="max-w-350 mx-auto px-6 pb-20">
    <h2 class="text-2xl font-extrabold text-center mb-12">
      Everything you need to <span class="text-accent-green">stay ahead</span> of earnings
    </h2>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div class="glass-card-solid rounded-2xl p-6">
        <div class="text-3xl mb-4">📅</div>
        <h3 class="font-bold text-lg mb-2">Weekly Calendar</h3>
        <p class="text-text-muted text-sm leading-relaxed">
          See every earnings report organized by day. Pre-market and after-hours reports clearly separated so you never miss a beat.
        </p>
      </div>

      <div class="glass-card-solid rounded-2xl p-6">
        <div class="text-3xl mb-4">🤖</div>
        <h3 class="font-bold text-lg mb-2">AI Analysis</h3>
        <p class="text-text-muted text-sm leading-relaxed">
          Click any reported stock to get instant AI-powered analysis — EPS surprise, revenue breakdown, guidance sentiment, and price reaction.
        </p>
      </div>

      <div class="glass-card-solid rounded-2xl p-6">
        <div class="text-3xl mb-4">⭐</div>
        <h3 class="font-bold text-lg mb-2">Watchlist</h3>
        <p class="text-text-muted text-sm leading-relaxed">
          Build a personal watchlist of stocks you care about. Favorite any ticker and see them front and center on your dashboard.
        </p>
      </div>
    </div>
  </section>

  <!-- CTA -->
  <section class="max-w-350 mx-auto px-6 pb-20">
    <div class="glass-card-solid rounded-3xl p-10 text-center glow-green">
      <h2 class="text-2xl font-extrabold mb-3">Ready to analyze earnings smarter?</h2>
      <p class="text-text-muted mb-6">Sign in with Google to get started in seconds.</p>
      <button
        class="px-8 py-3.5 text-base font-bold bg-accent-green border-none rounded-2xl text-white cursor-pointer transition-all hover:brightness-110 hover:shadow-[0_0_20px_rgba(52,172,86,0.4)]"
        onclick={signIn}
      >Sign in with Google</button>
    </div>
  </section>

  <!-- Footer -->
  <footer class="max-w-350 mx-auto px-6 py-8 text-center border-t border-border-subtle">
    <p class="text-text-muted text-xs">Earnings Analyzer — Powered by AI</p>
  </footer>
</div>
