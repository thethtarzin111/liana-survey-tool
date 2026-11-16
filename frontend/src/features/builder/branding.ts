// Branding swatches, limits and contrast checks, as in the prototype.
//
// The hex codes here are survey content (the colours a customer picks for their
// respondents' pages, stored per survey), not the admin app's own styling, so
// they are not design tokens.
/* eslint-disable no-restricted-syntax */

export const ACCENT_SWATCHES = [
  { name: 'Teal', hex: '#0F6A5E' },
  { name: 'Blue', hex: '#1B4F9C' },
  { name: 'Plum', hex: '#7A2E6E' },
  { name: 'Forest', hex: '#2F6B3A' },
];
export const DEFAULT_ACCENT = ACCENT_SWATCHES[0].hex; // Teal
export const BACKGROUND_SWATCHES = [
  { name: 'White', hex: '#FFFFFF' },
  { name: 'Light grey', hex: '#F6F7F9' },
  { name: 'Mint', hex: '#F0F9F6' },
  { name: 'Sand', hex: '#FAF6EE' },
];
export const DEFAULT_BACKGROUND = BACKGROUND_SWATCHES[0].hex; // White
/** Text colour on survey pages, used for the background contrast check. */
export const PAGE_TEXT = '#353A40';
export const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp'];
export const MAX_LOGO_BYTES = 1024 * 1024;
const MIN_CONTRAST = 4.5;

/** "2b6450" or "#2B6450" -> "#2B6450"; null when it is not a 6-digit hex code. */
export function hexOrNull(value: string): string | null {
  const match = /^#?([0-9a-f]{6})$/i.exec(value.trim());
  return match ? `#${match[1].toUpperCase()}` : null;
}

/** WCAG relative luminance of "#RRGGBB". */
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

/** The warning under the accent colour when white button text would be hard to read. */
export function accentWarning(accent: string): string | null {
  const ratio = contrast('#FFFFFF', accent);
  return ratio < MIN_CONTRAST
    ? `White text on this colour is hard to read (${ratio.toFixed(1)}:1, needs 4.5:1). Pick a darker shade so buttons stay readable.`
    : null;
}

/** The warning under the background colour when page text would be hard to read. */
export function backgroundWarning(background: string): string | null {
  const ratio = contrast(background, PAGE_TEXT);
  return ratio < MIN_CONTRAST
    ? `Text on this background is hard to read (${ratio.toFixed(1)}:1, needs 4.5:1). Pick a lighter shade.`
    : null;
}

/** Why a file cannot be a logo, or null when it can be uploaded. */
export function logoProblem(file: File): string | null {
  if (!LOGO_TYPES.includes(file.type)) return 'Choose an image file: PNG, JPG or SVG.';
  if (file.size > MAX_LOGO_BYTES) return 'The logo can be at most 1 MB.';
  return null;
}
