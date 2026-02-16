<script>
  import WeekCalendar from './components/WeekCalendar.svelte';
  import AnalysisModal from './components/AnalysisModal.svelte';
  import StockSearch from './components/StockSearch.svelte';
  import Homepage from './components/Homepage.svelte';
  import Toast from './components/Toast.svelte';
  import { initClerk, signIn, signOut } from './lib/clerk.js';
  import { fetchFavorites } from './lib/api.js';

  let analysisData = $state(null);
  let showModal = $state(false);
  let errorMessage = $state(null);
  let currentView = $state(getInitialView());

  let user = $state(null);
  let authReady = $state(false);
  let favorites = $state(new Set());

  function getInitialView() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('week')) return 'calendar';
    return 'home';
  }

  $effect(() => {
    initClerk().then((clerk) => {
      authReady = true;
      if (!clerk) return;

      user = clerk.user ?? null;
      if (user) loadFavorites();

      clerk.addListener(({ user: u }) => {
        user = u ?? null;
        if (user) loadFavorites();
        else favorites = new Set();
      });
    });
  });

  async function loadFavorites() {
    try {
      const favs = await fetchFavorites();
      favorites = new Set(favs.map(f => f.ticker));
    } catch {
      favorites = new Set();
    }
  }

  function handleFavoriteChange(ticker, added) {
    if (added) {
      favorites = new Set([...favorites, ticker]);
    } else {
      const next = new Set(favorites);
      next.delete(ticker);
      favorites = next;
    }
  }

  function handleShowAnalysis(event) {
    analysisData = event.detail;
    showModal = true;
  }

  function handleCloseModal() {
    showModal = false;
    analysisData = null;
  }

  function handleError(msg) {
    errorMessage = typeof msg === 'string' ? msg : msg?.detail ?? 'Something went wrong';
  }

  function navigateToCalendar(dateStr) {
    const url = new URL(window.location.href);
    url.searchParams.set('week', dateStr);
    window.history.pushState({}, '', url);
    currentView = 'calendar';
  }

  function navigateToHome() {
    const url = new URL(window.location.href);
    url.searchParams.delete('week');
    window.history.pushState({}, '', url);
    currentView = 'home';
  }

  $effect(() => {
    function handlePopState() {
      const params = new URLSearchParams(window.location.search);
      currentView = params.has('week') ? 'calendar' : 'home';
    }
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  });
</script>

<main class="max-w-350 mx-auto p-6 min-h-screen text-text-primary font-sans radial-gradient-bg">
  <header class="text-center mb-10 relative">
    <div class="absolute top-0 right-0">
      {#if authReady}
        {#if user}
          <div class="flex items-center gap-3">
            <span class="text-sm text-text-muted">{user.firstName ?? user.primaryEmailAddress?.emailAddress}</span>
            <button
              class="px-4 py-1.5 text-xs font-semibold bg-surface-card border border-border-subtle rounded-xl text-text-muted cursor-pointer transition-all hover:border-red-400/50 hover:text-red-400"
              onclick={signOut}
            >Sign out</button>
          </div>
        {:else}
          <button
            class="px-5 py-2 text-sm font-semibold bg-accent-green border-none rounded-xl text-white cursor-pointer transition-all hover:brightness-110"
            onclick={signIn}
          >Sign in</button>
        {/if}
      {/if}
    </div>
    <button class="bg-transparent border-none cursor-pointer" onclick={navigateToHome}>
      <h1 class="text-4xl font-extrabold mb-2 tracking-tight">
        <span class="text-accent-green">Earnings</span> Analyzer
      </h1>
    </button>
    <p class="text-text-muted text-sm tracking-wide">Track and analyze upcoming earnings reports</p>
  </header>

  <StockSearch onShowAnalysis={handleShowAnalysis} onError={handleError} />

  {#if currentView === 'home'}
    <Homepage onShowAnalysis={handleShowAnalysis} onNavigateToCalendar={navigateToCalendar} onError={handleError} {user} {favorites} onFavoriteChange={handleFavoriteChange} />
  {:else}
    <WeekCalendar onShowAnalysis={handleShowAnalysis} onError={handleError} {user} {favorites} onFavoriteChange={handleFavoriteChange} />
  {/if}

  {#if showModal && analysisData}
    <AnalysisModal data={analysisData} onClose={handleCloseModal} {user} isFavorited={favorites.has(analysisData.ticker)} onFavoriteChange={handleFavoriteChange} />
  {/if}

  {#if errorMessage}
    <Toast message={errorMessage} onDismiss={() => errorMessage = null} />
  {/if}
</main>
