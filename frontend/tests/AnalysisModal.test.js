import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import AnalysisModal from '../src/components/AnalysisModal.svelte';

vi.mock('../src/lib/api.js', () => ({
  addFavorite: vi.fn(),
  removeFavorite: vi.fn(),
}));

const baseData = {
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  quarter: 'Q4-2025',
  has_reported: true,
  eps_estimate: 2.35,
  eps_actual: 2.45,
  eps_surprise_pct: 4.26,
  revenue_estimate: 94900000000,
  revenue_actual: 95400000000,
  revenue_surprise_pct: 0.53,
  guidance_summary: 'Apple raised guidance for Q1 2026.',
  sentiment: 'bullish',
  sentiment_score: 0.85,
  price_reaction_pct: 3.2,
};

describe('AnalysisModal', () => {
  it('renders ticker, company name, and key metrics', () => {
    render(AnalysisModal, { props: { data: baseData, onClose: vi.fn() } });
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByText('$2.45')).toBeInTheDocument();
  });

  it('calls onClose when the close button is clicked', async () => {
    const onClose = vi.fn();
    render(AnalysisModal, { props: { data: baseData, onClose } });
    await fireEvent.click(screen.getByText('✕'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose on Escape key', async () => {
    const onClose = vi.fn();
    render(AnalysisModal, { props: { data: baseData, onClose } });
    const dialog = screen.getByRole('dialog');
    await fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('does not call onClose when clicking inside the dialog content', async () => {
    const onClose = vi.fn();
    render(AnalysisModal, { props: { data: baseData, onClose } });
    await fireEvent.click(screen.getByText('Apple Inc.'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('moves focus into the dialog on mount', () => {
    render(AnalysisModal, { props: { data: baseData, onClose: vi.fn() } });
    const dialog = screen.getByRole('dialog');
    expect(document.activeElement).toBe(dialog);
  });

  it('shows a pending-report notice when has_reported is false', () => {
    render(AnalysisModal, {
      props: { data: { ...baseData, has_reported: false }, onClose: vi.fn() },
    });
    expect(screen.getByText(/has not reported earnings yet/)).toBeInTheDocument();
  });

  it('shows limited-data notice when all financial fields are null', () => {
    render(AnalysisModal, {
      props: {
        data: {
          ...baseData,
          eps_estimate: null,
          eps_actual: null,
          revenue_estimate: null,
          revenue_actual: null,
        },
        onClose: vi.fn(),
      },
    });
    expect(screen.getByText(/Limited Data Available/)).toBeInTheDocument();
  });
});
