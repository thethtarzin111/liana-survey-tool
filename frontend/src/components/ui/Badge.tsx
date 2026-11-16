import type { ReactNode } from 'react';

export type BadgeTone = 'positive' | 'neutral' | 'negative' | 'outline' | 'muted';

/** Small rounded label. Tone carries meaning, so the text must say it too. */
export function Badge({ tone = 'neutral', children }: { tone?: BadgeTone; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export type SurveyStatus = 'draft' | 'scheduled' | 'live' | 'closed';

const STATUS: Record<SurveyStatus, { label: string; tone: BadgeTone }> = {
  live: { label: 'Live', tone: 'positive' },
  draft: { label: 'Draft', tone: 'neutral' },
  scheduled: { label: 'Scheduled', tone: 'outline' },
  closed: { label: 'Closed', tone: 'muted' },
};

/** Survey status with the prototype's colours (API values: draft, scheduled, live, closed). */
export function SurveyStatusBadge({ status }: { status: SurveyStatus }) {
  const s = STATUS[status];
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

/** Answer sentiment, e.g. NPS detractor / passive / promoter. */
export function SentimentBadge({ sentiment, children }: { sentiment: 'negative' | 'neutral' | 'positive'; children: ReactNode }) {
  return <Badge tone={sentiment}>{children}</Badge>;
}

/** Dark green number, e.g. "3" new contact requests. `label` is read out instead of the bare number. */
export function CountBadge({ count, label }: { count: number; label: string }) {
  return (
    <span className="count-badge" aria-label={label}>
      {count}
    </span>
  );
}

/** "New" marker next to a feature or item. */
export function NewBadge({ children = 'New' }: { children?: ReactNode }) {
  return <span className="new-badge">{children}</span>;
}

/** Pulsing dot with text, e.g. "Live · updated just now". */
export function LiveIndicator({ children }: { children: ReactNode }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
      <span className="live-dot" aria-hidden="true" />
      {children}
    </span>
  );
}
