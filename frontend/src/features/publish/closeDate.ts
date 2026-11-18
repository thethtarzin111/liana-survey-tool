/** "Closes on" is a day: the survey takes answers until that day ends, in the creator's time zone. */

function pad(n: number) {
  return String(n).padStart(2, '0');
}

/** "2026-12-31" → the ISO moment the next day starts, local time. */
export function closesAtFromDay(day: string): string {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(y, m - 1, d + 1).toISOString();
}

/** The ISO moment the survey closes → the last day it is open ("2026-12-31"). */
export function dayFromClosesAt(closesAt: string): string {
  const last = new Date(new Date(closesAt).getTime() - 1);
  return `${last.getFullYear()}-${pad(last.getMonth() + 1)}-${pad(last.getDate())}`;
}

/** Today as "YYYY-MM-DD", local time. */
export function today(now = new Date()): string {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
