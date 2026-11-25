import { ApiError, type LianaSendSettings } from '../../api/client';

export const DEMO_HOST = 'demo';
export const LIANA_HOST = 'rest.automation.lianacloud.com';

export const SEND_OPTIONS: { key: keyof LianaSendSettings; label: string; description: string }[] = [
  {
    key: 'answers',
    label: 'Answers',
    description: 'A survey_answered event with the score and NPS group, for segments such as “Survey detractors”.',
  },
  {
    key: 'contact_requests',
    label: '“Contact me” requests',
    description: 'A survey_contact_request event, so an automation can alert the account owner.',
  },
  {
    key: 'themes',
    label: 'Comment themes',
    description: 'The theme of each comment from Comment insights, sent as a second event later.',
  },
];

/** The API's message for a failed call, or a general one. */
export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  }
  return 'Something went wrong. Try again.';
}

/** "23 Nov 2026, 10:04" */
export function when(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
