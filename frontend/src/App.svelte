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

<main class="max-w-350 mx-auto p-6 min-h-screen bg-slate-900 text-slate-100 font-sans">
  <header class="text-center mb-8">
    <h1 class="text-3xl font-bold mb-1">📊 Earnings Analyzer</h1>
    <p class="text-slate-400 text-sm">Track and analyze upcoming earnings reports</p>
  </header>

  <WeekCalendar onShowAnalysis={handleShowAnalysis} />

  {#if showModal && analysisData}
    <AnalysisModal data={analysisData} onClose={handleCloseModal} />
  {/if}
</main>
