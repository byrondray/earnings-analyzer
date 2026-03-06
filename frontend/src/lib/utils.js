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

export function getDaysOfWeek(weekStart) {
  const days = [];
  const start = new Date(weekStart + 'T00:00:00');
  for (let i = 0; i < 5; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    days.push(d.toISOString().split('T')[0]);
  }
  return days;
}

export function isToday(dateStr) {
  const today = new Date().toISOString().split('T')[0];
  return dateStr === today;
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

export function getSentimentColor(sentiment) {
  if (sentiment === 'bullish') return '#34AC56';
  if (sentiment === 'bearish') return '#ef4444';
  return '#f59e0b';
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
