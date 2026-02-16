<script>
  import WeekCalendar from './components/WeekCalendar.svelte';
  import AnalysisModal from './components/AnalysisModal.svelte';
  import StockSearch from './components/StockSearch.svelte';
  import Homepage from './components/Homepage.svelte';

  let analysisData = $state(null);
  let showModal = $state(false);

  let currentView = $state(getInitialView());

  function getInitialView() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('week')) return 'calendar';
    return 'home';
  }

  function handleShowAnalysis(event) {
    analysisData = event.detail;
    showModal = true;
  }

  function handleCloseModal() {
    showModal = false;
    analysisData = null;
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
  <header class="text-center mb-10">
    <button class="bg-transparent border-none cursor-pointer" onclick={navigateToHome}>
      <h1 class="text-4xl font-extrabold mb-2 tracking-tight">
        <span class="text-accent-green">Earnings</span> Analyzer
      </h1>
    </button>
    <p class="text-text-muted text-sm tracking-wide">Track and analyze upcoming earnings reports</p>
  </header>

  <StockSearch onShowAnalysis={handleShowAnalysis} />

  {#if currentView === 'home'}
    <Homepage onShowAnalysis={handleShowAnalysis} onNavigateToCalendar={navigateToCalendar} />
  {:else}
    <WeekCalendar onShowAnalysis={handleShowAnalysis} />
  {/if}

  {#if showModal && analysisData}
    <AnalysisModal data={analysisData} onClose={handleCloseModal} />
  {/if}
</main>
