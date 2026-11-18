import { closesAtFromDay, dayFromClosesAt, today } from './closeDate';

test('a close day becomes the start of the next day, local time, and back', () => {
  const closesAt = closesAtFromDay('2026-12-31');
  expect(new Date(closesAt).getTime()).toBe(new Date(2027, 0, 1).getTime());
  expect(dayFromClosesAt(closesAt)).toBe('2026-12-31');
});

test('a close moment in the middle of a day shows that day', () => {
  expect(dayFromClosesAt(new Date(2026, 5, 3, 14, 30).toISOString())).toBe('2026-06-03');
});

test('today is padded', () => {
  expect(today(new Date(2026, 0, 5, 23, 59))).toBe('2026-01-05');
});
