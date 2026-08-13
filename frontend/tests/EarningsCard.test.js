import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import EarningsCard from '../src/components/EarningsCard.svelte';

vi.mock('../src/lib/api.js', () => ({
  fetchSparklines: vi.fn().mockResolvedValue({}),
  addFavorite: vi.fn(),
  removeFavorite: vi.fn(),
}));

function futureDateStr() {
  const d = new Date();
  d.setDate(d.getDate() + 30);
  return d.toISOString().slice(0, 10);
}

function pastDateStr() {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
}

const baseEvent = {
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  market_cap: 3_000_000_000_000,
  eps_estimate: 2.35,
  revenue_estimate: 94900000000,
};

describe('EarningsCard', () => {
  it('renders ticker and company name', () => {
    render(EarningsCard, {
      props: { event: { ...baseEvent, report_date: futureDateStr() }, onShowAnalysis: vi.fn() },
    });
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
  });

  it('shows "Upcoming" badge for a future report date', () => {
    render(EarningsCard, {
      props: { event: { ...baseEvent, report_date: futureDateStr() }, onShowAnalysis: vi.fn() },
    });
    expect(screen.getByText('Upcoming')).toBeInTheDocument();
  });

  it('shows "Reported" badge for a past report date', () => {
    render(EarningsCard, {
      props: { event: { ...baseEvent, report_date: pastDateStr() }, onShowAnalysis: vi.fn() },
    });
    expect(screen.getByText('Reported')).toBeInTheDocument();
  });

  it('calls onShowAnalysis with event details when clicked', async () => {
    const onShowAnalysis = vi.fn();
    render(EarningsCard, {
      props: {
        event: { ...baseEvent, report_date: futureDateStr(), fiscal_quarter: '2025-12-31' },
        onShowAnalysis,
      },
    });

    await fireEvent.click(screen.getByRole('button'));

    expect(onShowAnalysis).toHaveBeenCalledWith({
      detail: {
        ticker: 'AAPL',
        company_name: 'Apple Inc.',
        fiscal_quarter: '2025-12-31',
        report_date: expect.any(String),
      },
    });
  });

  it('omits optional fields when not present on the event', () => {
    render(EarningsCard, {
      props: {
        event: { ticker: 'ZZZZ', company_name: 'Unknown Co', report_date: futureDateStr() },
        onShowAnalysis: vi.fn(),
      },
    });
    expect(screen.queryByText(/Mkt Cap/)).not.toBeInTheDocument();
    expect(screen.queryByText(/EPS Est/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Rev Est/)).not.toBeInTheDocument();
  });
});
