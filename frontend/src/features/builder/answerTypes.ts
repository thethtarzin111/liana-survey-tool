import type { Question, QuestionInput, QuestionKind } from '../../api/client';

// Labels, hints and defaults follow the prototype's "Build your survey" screen.
// The rules the server checks are in survey_manager/questions/domain.py.

export const ANSWER_TYPES: { value: QuestionKind; label: string }[] = [
  { value: 'single_choice', label: 'Multiple choice' },
  { value: 'multiple_choice', label: 'Checkboxes' },
  { value: 'dropdown', label: 'Dropdown' },
  { value: 'text', label: 'Short answer' },
  { value: 'long_text', label: 'Paragraph' },
  { value: 'rating', label: 'Rating 1–5 (CSAT)' },
  { value: 'nps', label: 'NPS 0–10' },
  { value: 'reasons', label: 'Reason bubbles' },
];

export const CHOICE_KINDS = new Set<QuestionKind>(['single_choice', 'multiple_choice', 'dropdown', 'reasons']);
export const MAX_OPTIONS = 20;

export const NPS_PROMPT = 'How likely are you to recommend us to a friend or colleague?';
export const REASONS_HINT = 'Respondents tap one or more bubbles. Each bubble becomes a category in Top reasons.';
const DEFAULT_REASONS = ['Price', 'Quality', 'Customer service', 'Something else'];

export const SCALES: Partial<Record<QuestionKind, { numbers: number[]; hint: string }>> = {
  rating: {
    numbers: [1, 2, 3, 4, 5],
    hint: 'Standard CSAT scale: 1 Very dissatisfied to 5 Very satisfied. Score = % of 4–5 answers.',
  },
  nps: {
    numbers: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    hint: 'Standard NPS scale: 0 Not at all likely to 10 Extremely likely. The scale cannot be changed, so results stay comparable.',
  },
};

export const TEXT_HINTS: Partial<Record<QuestionKind, string>> = {
  text: 'Short answer text',
  long_text: 'Long answer text',
};

const isPlaceholderOption = (option: string) => /^Option \d+$/.test(option);

/** The text for a new option: "Option N" (or "New reason"), numbered past any already taken. */
export function newOptionText(kind: QuestionKind, options: string[]): string {
  const base = kind === 'reasons' ? 'New reason' : 'Option';
  const taken = new Set(options.map((o) => o.toLocaleLowerCase()));
  let n = kind === 'reasons' ? 1 : options.length + 1;
  const text = (i: number) => (kind === 'reasons' && i === 1 ? base : `${base} ${i}`);
  while (taken.has(text(n).toLocaleLowerCase())) n += 1;
  return text(n);
}

/** What to save when the answer type changes, as the prototype does it:
 *  NPS fills in the standard question if there is none; Reason bubbles replace
 *  untouched "Option N" placeholders with common reasons; a choice type coming
 *  from a type without options starts with "Option 1". */
export function changesForType(question: Question, kind: QuestionKind): Partial<QuestionInput> {
  const changes: Partial<QuestionInput> = { kind };
  if (kind === 'nps' && !question.prompt.trim()) changes.prompt = NPS_PROMPT;
  if (CHOICE_KINDS.has(kind)) {
    const hadOptions = CHOICE_KINDS.has(question.kind) && question.options.length > 0;
    if (kind === 'reasons' && (!hadOptions || question.options.every(isPlaceholderOption))) {
      changes.options = DEFAULT_REASONS;
    } else if (!hadOptions) {
      changes.options = ['Option 1'];
    }
  }
  return changes;
}
