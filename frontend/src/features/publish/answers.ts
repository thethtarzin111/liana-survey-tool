import type { SurveyType } from '../../api/client';

export type OneTapType = Exclude<SurveyType, 'custom'>;

/** One-tap answers per survey type, as in the email snippet (prototype). `value` goes in the link as `a=`. */
export const ANSWERS: Record<OneTapType, { value: number; label: string }[]> = {
  thumbs: [
    { value: 0, label: 'Not for me' },
    { value: 1, label: 'Good' },
    { value: 2, label: 'Loved it' },
  ],
  nps: Array.from({ length: 11 }, (_, i) => ({ value: i, label: String(i) })),
  csat: Array.from({ length: 5 }, (_, i) => ({ value: i + 1, label: String(i + 1) })),
};
