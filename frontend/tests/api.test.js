import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../src/lib/clerk.js', () => ({
  getToken: vi.fn().mockResolvedValue(null),
}));

import {
  fetchWeekEarnings,
  triggerAnalysis,
  getAnalysis,
} from '../src/lib/api.js';

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('fetchWeekEarnings', () => {
  it('calls correct endpoint with date param', async () => {
    const mockData = {
      week_start: '2026-02-16',
      week_end: '2026-02-20',
      events: [],
    };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData),
    });

    const result = await fetchWeekEarnings('2026-02-18');

    expect(fetch).toHaveBeenCalledWith('/api/calendar/week?date=2026-02-18', {
      cache: 'no-store',
    });
    expect(result).toEqual(mockData);
  });

  it('calls without date param when none provided', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ events: [] }),
    });

    await fetchWeekEarnings();

    expect(fetch).toHaveBeenCalledWith('/api/calendar/week', {
      cache: 'no-store',
    });
  });

  it('throws on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });

    await expect(fetchWeekEarnings('2026-02-18')).rejects.toThrow('500');
  });
});

function sseStreamResponse(events) {
  const body = events
    .map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    .join('');
  const chunks = [new TextEncoder().encode(body)];

  return {
    ok: true,
    body: {
      getReader() {
        let done = false;
        return {
          read: async () => {
            if (done) return { done: true, value: undefined };
            done = true;
            return { done: false, value: chunks[0] };
          },
        };
      },
    },
  };
}

describe('triggerAnalysis', () => {
  it('posts to correct endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      sseStreamResponse([
        { event: 'status', data: { message: 'Starting...' } },
        { event: 'result', data: { ticker: 'AAPL', eps_actual: 2.45 } },
      ]),
    );

    const result = await triggerAnalysis('AAPL', 'Q4-2025');

    expect(fetch).toHaveBeenCalledWith(
      '/api/analysis/AAPL?quarter=Q4-2025',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(result.ticker).toBe('AAPL');
  });

  it('throws on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 502 });

    await expect(triggerAnalysis('AAPL', 'Q4-2025')).rejects.toThrow('502');
  });

  it('throws on error event', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      sseStreamResponse([
        { event: 'error', data: { error: 'Analysis failed: boom' } },
      ]),
    );

    await expect(triggerAnalysis('AAPL', 'Q4-2025')).rejects.toThrow(
      'Analysis failed: boom',
    );
  });
});

describe('getAnalysis', () => {
  it('returns null on 404', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });

    const result = await getAnalysis('XYZ');

    expect(result).toBeNull();
  });

  it('returns data on success', async () => {
    const mockData = { ticker: 'AAPL', sentiment: 'bullish' };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData),
    });

    const result = await getAnalysis('AAPL');

    expect(result.sentiment).toBe('bullish');
  });
});
