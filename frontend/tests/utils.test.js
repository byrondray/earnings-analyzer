import { describe, it, expect } from 'vitest';
import {
  getWeekBounds,
  formatDate,
  groupByDate,
  getDaysOfWeek,
  isToday,
  formatReportTime,
  formatLargeNumber,
  formatPercent,
} from '../src/lib/utils.js';

function toLocalDateStr(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

describe('getWeekBounds', () => {
  it('returns monday and friday for a wednesday', () => {
    const { monday, friday } = getWeekBounds('2026-02-18');
    expect(toLocalDateStr(monday)).toBe('2026-02-16');
    expect(toLocalDateStr(friday)).toBe('2026-02-20');
  });

  it('returns same day for monday input', () => {
    const { monday } = getWeekBounds('2026-02-16');
    expect(toLocalDateStr(monday)).toBe('2026-02-16');
  });

  it('handles sunday correctly', () => {
    const { monday } = getWeekBounds('2026-02-15');
    expect(toLocalDateStr(monday)).toBe('2026-02-09');
  });
});

describe('groupByDate', () => {
  it('groups events by report_date', () => {
    const events = [
      { ticker: 'AAPL', report_date: '2026-02-16' },
      { ticker: 'MSFT', report_date: '2026-02-16' },
      { ticker: 'GOOGL', report_date: '2026-02-17' },
    ];
    const result = groupByDate(events);
    expect(Object.keys(result)).toHaveLength(2);
    expect(result['2026-02-16']).toHaveLength(2);
    expect(result['2026-02-17']).toHaveLength(1);
  });

  it('returns empty object for empty array', () => {
    expect(groupByDate([])).toEqual({});
  });
});

describe('getDaysOfWeek', () => {
  it('returns 5 consecutive days starting from week start', () => {
    const days = getDaysOfWeek('2026-02-16');
    expect(days).toHaveLength(5);
    expect(days[0]).toBe('2026-02-16');
    expect(days[4]).toBe('2026-02-20');
  });
});

describe('formatReportTime', () => {
  it('maps pre_market correctly', () => {
    expect(formatReportTime('pre_market')).toBe('Before Market');
  });

  it('maps post_market correctly', () => {
    expect(formatReportTime('post_market')).toBe('After Market');
  });

  it('maps unknown to TBD', () => {
    expect(formatReportTime('unknown')).toBe('TBD');
  });
});

describe('formatLargeNumber', () => {
  it('formats billions', () => {
    expect(formatLargeNumber(94900000000)).toBe('$94.90B');
  });

  it('formats millions', () => {
    expect(formatLargeNumber(5500000)).toBe('$5.50M');
  });

  it('formats trillions', () => {
    expect(formatLargeNumber(1500000000000)).toBe('$1.50T');
  });

  it('returns N/A for null', () => {
    expect(formatLargeNumber(null)).toBe('N/A');
  });
});

describe('formatPercent', () => {
  it('formats positive with plus sign', () => {
    expect(formatPercent(4.26)).toBe('+4.26%');
  });

  it('formats negative with minus sign', () => {
    expect(formatPercent(-2.1)).toBe('-2.10%');
  });

  it('returns N/A for null', () => {
    expect(formatPercent(null)).toBe('N/A');
  });
});

describe('isToday', () => {
  it('returns true for today', () => {
    const today = new Date().toISOString().split('T')[0];
    expect(isToday(today)).toBe(true);
  });

  it('returns false for a different date', () => {
    expect(isToday('2020-01-01')).toBe(false);
  });
});
