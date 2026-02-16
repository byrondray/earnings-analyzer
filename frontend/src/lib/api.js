const API_BASE = '/api';

export async function fetchWeekEarnings(dateStr = null) {
  const params = dateStr ? `?date=${dateStr}` : '';
  const res = await fetch(`${API_BASE}/calendar/week${params}`);
  if (!res.ok) throw new Error(`Failed to fetch earnings: ${res.status}`);
  return res.json();
}

export async function fetchNextWeek(dateStr = null) {
  const params = dateStr ? `?date=${dateStr}` : '';
  const res = await fetch(`${API_BASE}/calendar/week/next${params}`);
  if (!res.ok) throw new Error(`Failed to fetch next week: ${res.status}`);
  return res.json();
}

export async function fetchPrevWeek(dateStr = null) {
  const params = dateStr ? `?date=${dateStr}` : '';
  const res = await fetch(`${API_BASE}/calendar/week/prev${params}`);
  if (!res.ok) throw new Error(`Failed to fetch prev week: ${res.status}`);
  return res.json();
}

export async function triggerAnalysis(ticker, quarter) {
  const res = await fetch(
    `${API_BASE}/analysis/${ticker}?quarter=${encodeURIComponent(quarter)}`,
    {
      method: 'POST',
    },
  );
  if (!res.ok) throw new Error(`Analysis failed: ${res.status}`);
  return res.json();
}

export async function getAnalysis(ticker) {
  const res = await fetch(`${API_BASE}/analysis/${ticker}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to get analysis: ${res.status}`);
  return res.json();
}

export async function searchStock(ticker) {
  const res = await fetch(
    `${API_BASE}/calendar/search?ticker=${encodeURIComponent(ticker)}`,
  );
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}
