import { describe, it, expect, vi, beforeEach } from 'vitest';
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

    expect(fetch).toHaveBeenCalledWith('/api/calendar/week?date=2026-02-18');
    expect(result).toEqual(mockData);
  });

  it('calls without date param when none provided', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ events: [] }),
    });

    await fetchWeekEarnings();

    expect(fetch).toHaveBeenCalledWith('/api/calendar/week');
  });

  it('throws on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });

    await expect(fetchWeekEarnings('2026-02-18')).rejects.toThrow('500');
  });
});

describe('triggerAnalysis', () => {
  it('posts to correct endpoint', async () => {
    const mockResult = { ticker: 'AAPL', eps_actual: 2.45 };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResult),
    });

    const result = await triggerAnalysis('AAPL', 'Q4-2025');

    expect(fetch).toHaveBeenCalledWith('/api/analysis/AAPL?quarter=Q4-2025', {
      method: 'POST',
    });
    expect(result.ticker).toBe('AAPL');
  });

  it('throws on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 502 });

    await expect(triggerAnalysis('AAPL', 'Q4-2025')).rejects.toThrow('502');
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
