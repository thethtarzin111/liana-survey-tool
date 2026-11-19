export type Tone = 'negative' | 'neutral' | 'positive' | number;

/** The class that colours a slice or bar; numbers pick from the series colours. */
export function toneClass(tone: Tone): string {
  return typeof tone === 'number' ? `tone-series-${tone % 5}` : `tone-${tone}`;
}

export const percentOf = (part: number, whole: number) => (whole ? Math.round((part / whole) * 100) : 0);
