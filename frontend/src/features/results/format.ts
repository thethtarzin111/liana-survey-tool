import type { SurveyType } from '../../api/client';

export const TYPE_LABEL: Record<SurveyType, string> = {
  thumbs: 'Thumbs rating',
  nps: 'NPS survey',
  csat: 'CSAT survey',
  custom: 'Custom survey',
};

/** `plural(1, 'answer', 'answers')` is "1 answer". */
export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** "+40", "−33" (a real minus sign) or "0". */
export function signed(n: number): string {
  if (n > 0) return `+${n}`;
  if (n < 0) return `−${Math.abs(n)}`;
  return '0';
}

/** "Mon 01/12/2026" */
export function dayDate(iso: string): string {
  const d = new Date(iso);
  const weekday = d.toLocaleDateString('en-GB', { weekday: 'short' });
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${weekday} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "12 min ago", "2 h ago", "3 days ago"; a date once it is a week old. */
export function relativeTime(iso: string, now = Date.now()): string {
  const age = Math.max(0, now - new Date(iso).getTime());
  if (age < MINUTE) return 'just now';
  if (age < HOUR) return `${Math.floor(age / MINUTE)} min ago`;
  if (age < DAY) return `${Math.floor(age / HOUR)} h ago`;
  if (age < 7 * DAY) return `${plural(Math.floor(age / DAY), 'day', 'days')} ago`;
  return dayDate(iso);
}
