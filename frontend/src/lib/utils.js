export function getWeekBounds(date) {
  const d = new Date(date + 'T00:00:00');
  const day = d.getDay();
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const monday = new Date(d);
  monday.setDate(d.getDate() + diffToMonday);

  const friday = new Date(monday);
  friday.setDate(monday.getDate() + 4);

  return { monday, friday };
}

export function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

export function formatDateShort(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function groupByDate(events) {
  const groups = {};
  for (const event of events) {
    const key = event.report_date;
    if (!groups[key]) groups[key] = [];
    groups[key].push(event);
  }
  return groups;
}

export function toLocalDateKey(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function getDaysOfWeek(weekStart) {
  const days = [];
  const start = new Date(weekStart + 'T00:00:00');
  for (let i = 0; i < 7; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    days.push(toLocalDateKey(d));
  }
  return days;
}

export function isToday(dateStr) {
  return dateStr === toLocalDateKey(new Date());
}

export function todayKey() {
  return toLocalDateKey(new Date());
}

export function formatReportTime(time) {
  if (time === 'pre_market') return 'Before Market';
  if (time === 'post_market') return 'After Market';
  return 'TBD';
}

export function formatLargeNumber(num) {
  if (num == null) return 'N/A';
  if (Math.abs(num) >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  return `$${num.toFixed(2)}`;
}

export function formatPercent(num) {
  if (num == null) return 'N/A';
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(2)}%`;
}

export const SENTIMENT_COLORS = {
  bullish: '#34AC56',
  bearish: '#ef4444',
  neutral: '#f59e0b',
};

export const UP_COLOR = '#34AC56';
export const DOWN_COLOR = '#ef4444';

export function getSentimentColor(sentiment) {
  return SENTIMENT_COLORS[sentiment] ?? SENTIMENT_COLORS.neutral;
}

export function formatWeekRange(start, end) {
  const s = new Date(start + 'T00:00:00');
  const e = new Date(end + 'T00:00:00');
  return `${s.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })} – ${e.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`;
}

export function getSentimentEmoji(sentiment) {
  if (sentiment === 'bullish') return '🟢';
  if (sentiment === 'bearish') return '🔴';
  return '🟡';
}

export function formatDateReadable(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function formatNewsDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const now = new Date();
  const diff = now - d;
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return 'Just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}
