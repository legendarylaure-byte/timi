function formatTime(timestamp: any): string {
  if (!timestamp) return '';
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;

  const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
  if (date.getFullYear() !== now.getFullYear()) opts.year = 'numeric';
  return date.toLocaleDateString('en-US', opts);
}

describe('formatTime', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2026-06-27T12:00:00Z'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('returns empty string for null/undefined', () => {
    expect(formatTime(null)).toBe('');
    expect(formatTime(undefined)).toBe('');
  });

  it('returns "just now" for timestamps < 60s ago', () => {
    const recent = new Date('2026-06-27T11:59:30Z');
    expect(formatTime(recent)).toBe('just now');
  });

  it('returns "Xm ago" for timestamps < 1h ago', () => {
    const tenMinAgo = new Date('2026-06-27T11:50:00Z');
    expect(formatTime(tenMinAgo)).toBe('10m ago');
  });

  it('returns "Xh ago" for timestamps < 24h ago', () => {
    const threeHAgo = new Date('2026-06-27T09:00:00Z');
    expect(formatTime(threeHAgo)).toBe('3h ago');
  });

  it('returns date string for timestamps > 24h', () => {
    const yesterday = new Date('2026-06-26T12:00:00Z');
    const result = formatTime(yesterday);
    expect(result).toContain('Jun');
    expect(result).toContain('26');
  });

  it('returns date with year for different year', () => {
    const lastYear = new Date('2025-12-01T12:00:00Z');
    const result = formatTime(lastYear);
    expect(result).toContain('2025');
  });
});
