<script>
  import WeekCalendar from './components/WeekCalendar.svelte';
  import AnalysisModal from './components/AnalysisModal.svelte';

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

<main>
  <header>
    <h1>📊 Earnings Analyzer</h1>
    <p class="subtitle">Track and analyze upcoming earnings reports</p>
  </header>

  <WeekCalendar onShowAnalysis={handleShowAnalysis} />

  {#if showModal && analysisData}
    <AnalysisModal data={analysisData} onClose={handleCloseModal} />
  {/if}
</main>
