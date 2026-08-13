import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import StockSearch from '../src/components/StockSearch.svelte';
import { searchStock } from '../src/lib/api.js';

vi.mock('../src/lib/api.js', () => ({
  searchStock: vi.fn(),
  fetchSparklines: vi.fn().mockResolvedValue({}),
  addFavorite: vi.fn(),
  removeFavorite: vi.fn(),
}));

beforeEach(() => {
  searchStock.mockReset();
});

describe('StockSearch', () => {
  it('does not call searchStock for an empty query', async () => {
    render(StockSearch, { props: { onShowAnalysis: vi.fn() } });
    const form = screen.getByRole('button', { name: /search/i }).closest('form');
    await fireEvent.submit(form);
    expect(searchStock).not.toHaveBeenCalled();
  });

  it('calls searchStock with the trimmed ticker and renders results', async () => {
    searchStock.mockResolvedValue({
      ticker: 'AAPL',
      events: [
        {
          ticker: 'AAPL',
          company_name: 'Apple Inc.',
          report_date: '2026-02-16',
          report_time: 'pre_market',
          eps_estimate: 2.35,
        },
      ],
    });

    render(StockSearch, { props: { onShowAnalysis: vi.fn() } });
    const input = screen.getByPlaceholderText(/search stock ticker/i);
    await fireEvent.input(input, { target: { value: '  aapl  ' } });
    await fireEvent.submit(input.closest('form'));

    expect(searchStock).toHaveBeenCalledWith('aapl');
    await waitFor(() => {
      expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    });
  });

  it('shows a no-results message when the search returns no events', async () => {
    searchStock.mockResolvedValue({ ticker: 'ZZZZ', events: [] });

    render(StockSearch, { props: { onShowAnalysis: vi.fn() } });
    const input = screen.getByPlaceholderText(/search stock ticker/i);
    await fireEvent.input(input, { target: { value: 'zzzz' } });
    await fireEvent.submit(input.closest('form'));

    await waitFor(() => {
      expect(screen.getByText(/No upcoming earnings found for ZZZZ/)).toBeInTheDocument();
    });
  });

  it('calls onError when the search fails', async () => {
    searchStock.mockRejectedValue(new Error('Failed to search for ticker'));
    const onError = vi.fn();

    render(StockSearch, { props: { onShowAnalysis: vi.fn(), onError } });
    const input = screen.getByPlaceholderText(/search stock ticker/i);
    await fireEvent.input(input, { target: { value: 'aapl' } });
    await fireEvent.submit(input.closest('form'));

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith('Failed to search for ticker');
    });
  });

  it('clears results when the clear button is clicked', async () => {
    searchStock.mockResolvedValue({
      ticker: 'AAPL',
      events: [{ ticker: 'AAPL', company_name: 'Apple Inc.', report_date: '2026-02-16', report_time: 'pre_market' }],
    });

    render(StockSearch, { props: { onShowAnalysis: vi.fn() } });
    const input = screen.getByPlaceholderText(/search stock ticker/i);
    await fireEvent.input(input, { target: { value: 'aapl' } });
    await fireEvent.submit(input.closest('form'));

    await waitFor(() => expect(screen.getByText('Apple Inc.')).toBeInTheDocument());

    await fireEvent.click(screen.getByText('Clear'));

    expect(screen.queryByText('Apple Inc.')).not.toBeInTheDocument();
  });
});
