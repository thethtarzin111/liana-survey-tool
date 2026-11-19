import type { SurveyOverview } from '../../api/client';
import { dayDate, relativeTime } from './format';

type Channel = SurveyOverview['channels'][number];
// The first channel starts the sentence; the others follow after a comma.
const CHANNEL_FIRST: Record<Channel, string> = { email: 'Sent by email', link: 'Shared by link', qr: 'QR code' };
const CHANNEL_NEXT: Record<Channel, string> = { email: 'sent by email', link: 'shared by link', qr: 'QR code' };
const STATE_TEXT = { live: 'Collecting answers', closed: 'Closed', scheduled: 'Scheduled', draft: 'Draft' } as const;

/** "Collecting answers · last one 2 h ago · Closes Thu 31/12/2026 · Shared by link" */
export function StatusLine({ overview }: { overview: SurveyOverview }) {
  const { status, last_answer_at, closes_at, channels } = overview;
  const parts = [STATE_TEXT[status], last_answer_at ? `last one ${relativeTime(last_answer_at)}` : 'no answers yet'];
  if (closes_at && (status === 'live' || status === 'scheduled')) parts.push(`Closes ${dayDate(closes_at)}`);
  if (channels.length) {
    parts.push(channels.map((c, i) => (i === 0 ? CHANNEL_FIRST[c] : CHANNEL_NEXT[c])).join(', '));
  }
  return (
    <p className="results-status" data-testid="status-line">
      {status === 'live' ? <span className="live-dot" aria-hidden="true" /> : null}
      {parts.map((part, i) => (
        <span key={part}>
          {i > 0 ? <span aria-hidden="true"> · </span> : null}
          {part}
        </span>
      ))}
    </p>
  );
}
