import { dayDate, plural, relativeTime, signed } from './format';

test('plural counts with the right word', () => {
  expect(plural(1, 'answer', 'answers')).toBe('1 answer');
  expect(plural(0, 'answer', 'answers')).toBe('0 answers');
  expect(plural(2, 'answer', 'answers')).toBe('2 answers');
});

test('signed shows a plus, a real minus sign or a bare zero', () => {
  expect(signed(40)).toBe('+40');
  expect(signed(-33)).toBe('−33');
  expect(signed(0)).toBe('0');
});

test('dayDate is weekday and day/month/year', () => {
  expect(dayDate('2026-12-01T12:00:00')).toBe('Tue 01/12/2026');
});

test('relativeTime counts minutes, hours and days back', () => {
  const now = new Date('2026-11-19T12:00:00Z').getTime();
  expect(relativeTime('2026-11-19T11:59:40Z', now)).toBe('just now');
  expect(relativeTime('2026-11-19T11:48:00Z', now)).toBe('12 min ago');
  expect(relativeTime('2026-11-19T10:00:00Z', now)).toBe('2 h ago');
  expect(relativeTime('2026-11-18T10:00:00Z', now)).toBe('1 day ago');
  expect(relativeTime('2026-11-14T10:00:00Z', now)).toBe('5 days ago');
  expect(relativeTime('2026-09-01T10:00:00Z', now)).toBe('Tue 01/09/2026');
});
