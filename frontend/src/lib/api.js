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

export async function triggerAnalysis(ticker, quarter, onStatus) {
  const res = await fetch(
    `${API_BASE}/analysis/${ticker}?quarter=${encodeURIComponent(quarter)}`,
    {
      method: 'POST',
      headers: { Accept: 'text/event-stream' },
    },
  );
  if (!res.ok) throw new Error(`Analysis failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();

    let eventType = null;
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith('data: ') && eventType) {
        const data = JSON.parse(line.slice(6));
        if (eventType === 'status' && onStatus) {
          onStatus(data.message);
        } else if (eventType === 'result') {
          result = data;
        } else if (eventType === 'error') {
          throw new Error(data.error || 'Analysis failed');
        }
        eventType = null;
      }
    }
  }

  if (!result) throw new Error('No analysis result received');
  return result;
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
