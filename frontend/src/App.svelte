<script>
  import WeekCalendar from './components/WeekCalendar.svelte';
  import AnalysisModal from './components/AnalysisModal.svelte';
  import StockSearch from './components/StockSearch.svelte';

  let analysisData = $state(null);
  let showModal = $state(false);

  function handleShowAnalysis(event) {
    analysisData = event.detail;
    showModal = true;
  }

  function handleCloseModal() {
    showModal = false;
    analysisData = null;
  }
</script>

<main class="max-w-350 mx-auto p-6 min-h-screen text-text-primary font-sans radial-gradient-bg">
  <header class="text-center mb-10">
    <h1 class="text-4xl font-extrabold mb-2 tracking-tight">
      <span class="text-accent-green">Earnings</span> Analyzer
    </h1>
    <p class="text-text-muted text-sm tracking-wide">Track and analyze upcoming earnings reports</p>
  </header>

  <StockSearch onShowAnalysis={handleShowAnalysis} />

  <WeekCalendar onShowAnalysis={handleShowAnalysis} />

  {#if showModal && analysisData}
    <AnalysisModal data={analysisData} onClose={handleCloseModal} />
  {/if}
</main>
