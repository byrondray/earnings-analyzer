import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/svelte';
import WeekCalendar from '../src/components/WeekCalendar.svelte';
import { fetchWeekEarnings } from '../src/lib/api.js';

vi.mock('../src/lib/api.js', () => ({
  fetchWeekEarnings: vi.fn(),
  fetchSparklines: vi.fn().mockResolvedValue({}),
  addFavorite: vi.fn(),
  removeFavorite: vi.fn(),
}));

const sampleWeek = {
  week_start: '2026-02-16',
  week_end: '2026-02-22',
  events: [
    {
      ticker: 'AAPL',
      company_name: 'Apple Inc.',
      report_date: '2026-02-16',
      report_time: 'pre_market',
      eps_estimate: 2.35,
    },
    {
      ticker: 'MSFT',
      company_name: 'Microsoft Corporation',
      report_date: '2026-02-17',
      report_time: 'post_market',
      eps_estimate: 3.12,
    },
  ],
};

beforeEach(() => {
  fetchWeekEarnings.mockReset();
  window.history.replaceState({}, '', '/');
});

describe('WeekCalendar', () => {
  it('shows a loading skeleton before data resolves', () => {
    fetchWeekEarnings.mockReturnValue(new Promise(() => {}));
    render(WeekCalendar, { props: { onShowAnalysis: vi.fn() } });
    // 7 skeleton placeholders are rendered while loading
    expect(document.querySelectorAll('.animate-\\[pulse-skeleton_1\\.5s_ease-in-out_infinite\\]').length).toBe(7);
  });

  it('renders events grouped into day columns once loaded', async () => {
    fetchWeekEarnings.mockResolvedValue(sampleWeek);
    render(WeekCalendar, { props: { onShowAnalysis: vi.fn() } });

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
    });
    expect(screen.getByText('2 earnings reports')).toBeInTheDocument();
  });

  it('shows an error state with a retry button when the fetch fails', async () => {
    fetchWeekEarnings.mockRejectedValue(new Error('Failed to fetch earnings calendar'));
    render(WeekCalendar, { props: { onShowAnalysis: vi.fn() } });

    await waitFor(() => {
      expect(screen.getByText(/Failed to fetch earnings calendar/)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('retry re-invokes fetchWeekEarnings', async () => {
    fetchWeekEarnings.mockRejectedValueOnce(new Error('boom'));
    render(WeekCalendar, { props: { onShowAnalysis: vi.fn() } });

    await waitFor(() => expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument());

    fetchWeekEarnings.mockResolvedValueOnce(sampleWeek);
    await fireEvent.click(screen.getByRole('button', { name: /retry/i }));

    await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
    expect(fetchWeekEarnings).toHaveBeenCalledTimes(2);
  });

  it('disables nav buttons while loading', () => {
    fetchWeekEarnings.mockReturnValue(new Promise(() => {}));
    render(WeekCalendar, { props: { onShowAnalysis: vi.fn() } });

    expect(screen.getByRole('button', { name: /prev week/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /today/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /next week/i })).toBeDisabled();
  });
});
