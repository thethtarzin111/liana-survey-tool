import type { Tone } from './charts/tone';

export type Group = { label: string; values: string[]; tone: Tone };

const range = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => String(from + i));

export const NPS_GROUPS: Group[] = [
  { label: 'Detractors', values: range(0, 6), tone: 'negative' },
  { label: 'Passives', values: range(7, 8), tone: 'neutral' },
  { label: 'Promoters', values: range(9, 10), tone: 'positive' },
];
export const RATING_GROUPS: Group[] = [
  { label: 'Unsatisfied', values: range(1, 2), tone: 'negative' },
  { label: 'Neutral', values: ['3'], tone: 'neutral' },
  { label: 'Satisfied', values: range(4, 5), tone: 'positive' },
];
export const THUMBS_GROUPS: Group[] = [
  { label: 'Not for me', values: ['0'], tone: 'negative' },
  { label: 'Good', values: ['1'], tone: 'neutral' },
  { label: 'Loved it', values: ['2'], tone: 'positive' },
];

export const groupsFor = (kind: 'nps' | 'thumbs' | 'rating') =>
  kind === 'nps' ? NPS_GROUPS : kind === 'thumbs' ? THUMBS_GROUPS : RATING_GROUPS;

export const scaleValues = (kind: 'nps' | 'thumbs' | 'rating') =>
  kind === 'nps' ? range(0, 10) : kind === 'thumbs' ? range(0, 2) : range(1, 5);

/** The group that a scale value belongs to. */
export function toneOf(kind: 'nps' | 'thumbs' | 'rating', value: string): Tone {
  return groupsFor(kind).find((g) => g.values.includes(value))?.tone ?? 'neutral';
}

export const THUMBS_LABEL: Record<string, string> = { '0': 'Not for me', '1': 'Good', '2': 'Loved it' };
