import { ACCENT_SWATCHES, BACKGROUND_SWATCHES, accentWarning, backgroundWarning, contrast, hexOrNull, logoProblem } from './branding';

/* eslint-disable no-restricted-syntax -- colours here are test data */

test('hex codes are normalised or refused', () => {
  expect(hexOrNull('2b6450')).toBe('#2B6450');
  expect(hexOrNull(' #2B6450 ')).toBe('#2B6450');
  for (const bad of ['#FFF', 'teal', '#12345G', '']) expect(hexOrNull(bad)).toBeNull();
});

test('contrast follows WCAG', () => {
  expect(contrast('#FFFFFF', '#000000')).toBeCloseTo(21, 0);
  expect(contrast('#FFFFFF', '#FFFFFF')).toBeCloseTo(1, 5);
});

test('the prototype swatches pass their contrast checks', () => {
  for (const { hex } of ACCENT_SWATCHES) expect(accentWarning(hex)).toBeNull();
  for (const { hex } of BACKGROUND_SWATCHES) expect(backgroundWarning(hex)).toBeNull();
});

test('light accents and dark backgrounds get the prototype warnings', () => {
  expect(accentWarning('#F6F7F9')).toMatch(/^White text on this colour is hard to read \(1\.\d:1, needs 4\.5:1\)\. Pick a darker shade so buttons stay readable\.$/);
  expect(backgroundWarning('#353A40')).toBe('Text on this background is hard to read (1.0:1, needs 4.5:1). Pick a lighter shade.');
});

test('logos must be an accepted image of at most 1 MB', () => {
  const file = (type: string, size = 10) => new File([new Uint8Array(size)], 'logo', { type });
  expect(logoProblem(file('image/png'))).toBeNull();
  expect(logoProblem(file('image/svg+xml'))).toBeNull();
  expect(logoProblem(file('image/gif'))).toBe('Choose an image file: PNG, JPG or SVG.');
  expect(logoProblem(file('image/png', 1024 * 1024 + 1))).toBe('The logo can be at most 1 MB.');
});
