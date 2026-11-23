import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  api,
  type ContactRequest,
  type ContactRequestList,
  type ContactRequestStatus,
} from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Select,
  SentimentBadge,
  Table,
  ToggleChip,
  icons,
  useToast,
  type BadgeTone,
  type Column,
} from '../../components/ui';
import { relativeTime } from '../results/format';
import { THUMBS_LABEL, toneOf } from '../results/groups';
import './contact-requests.css';

export const STATUS_LABEL: Record<ContactRequestStatus, string> = {
  new: 'New',
  contacted: 'Contacted',
  done: 'Done',
};
const STATUSES = Object.keys(STATUS_LABEL) as ContactRequestStatus[];

const LIANA: Record<ContactRequest['liana_status'], { label: string; tone: BadgeTone }> = {
  sent: { label: 'In LianaAutomation', tone: 'muted' },
  pending: { label: 'Sending to LianaAutomation', tone: 'outline' },
  failed: { label: 'Not sent to LianaAutomation', tone: 'negative' },
};

const isStatus = (value: string | null): value is ContactRequestStatus =>
  value !== null && (STATUSES as string[]).includes(value);

/** The reader's answer as on Results: "Not for me" for thumbs, the score otherwise. */
export function AnswerBadge({ row }: { row: Pick<ContactRequest, 'answer' | 'survey_type'> }) {
  if (row.answer === null || row.survey_type === 'custom') return <span className="cr-none">—</span>;
  const kind = row.survey_type === 'csat' ? 'rating' : row.survey_type;
  const value = String(row.answer);
  const text = kind === 'thumbs' ? (THUMBS_LABEL[value] ?? value) : kind === 'rating' ? `${value}/5` : value;
  const tone = toneOf(kind, value);
  return <SentimentBadge sentiment={typeof tone === 'number' ? 'neutral' : tone}>{text}</SentimentBadge>;
}

/** Whether the request reached LianaAutomation. */
export function LianaBadge({ status }: { status: ContactRequest['liana_status'] }) {
  const s = LIANA[status];
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

type Load = { state: 'loading' } | { state: 'failed' } | { state: 'ready'; data: ContactRequestList };

/** Readers who ticked "Contact me", with a status the team updates as it replies. */
export function ContactRequestsPage() {
  const [params, setParams] = useSearchParams();
  const raw = params.get('status');
  const status = isStatus(raw) ? raw : null;
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [reload, setReload] = useState(0);
  const [saving, setSaving] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    let active = true;
    api.contactRequests({ status: status ?? undefined }).then(
      (data) => { if (active) setLoad({ state: 'ready', data }); },
      () => { if (active) setLoad({ state: 'failed' }); },
    );
    return () => { active = false; };
  }, [status, reload]);

  const pick = (next: ContactRequestStatus | null) => {
    const copy = new URLSearchParams(params);
    if (next) copy.set('status', next);
    else copy.delete('status');
    setParams(copy, { replace: true });
  };

  const change = (row: ContactRequest, next: ContactRequestStatus) => {
    setSaving(row.id);
    api.setContactRequestStatus(row.id, next).then(
      () => {
        setSaving(null);
        toast(`${row.contact_ref}: marked as ${STATUS_LABEL[next].toLowerCase()}.`);
        setReload((n) => n + 1);
      },
      () => {
        setSaving(null);
        toast('Could not change the status. Please try again.');
      },
    );
  };

  const columns: Column<ContactRequest>[] = [
    {
      key: 'respondent',
      header: 'Respondent',
      render: (r) => (
        <div className="cr-respondent">
          <strong>{r.contact_ref}</strong>
          <span className="cr-meta">{relativeTime(r.created_at)}</span>
          <LianaBadge status={r.liana_status} />
        </div>
      ),
    },
    { key: 'answer', header: 'Answer', render: (r) => <AnswerBadge row={r} /> },
    { key: 'reason', header: 'Reason', render: (r) => r.reason ?? <span className="cr-none">—</span> },
    {
      key: 'survey',
      header: 'Survey',
      render: (r) => <Link to={`/results?survey=${encodeURIComponent(r.survey_id)}`}>{r.survey_title}</Link>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) => (
        <Select
          label={`Status for ${r.contact_ref}`}
          hideLabel
          className="cr-status"
          value={r.status}
          disabled={saving === r.id}
          options={STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))}
          onChange={(e) => change(r, e.target.value as ContactRequestStatus)}
        />
      ),
    },
  ];

  let body;
  if (load.state === 'failed') {
    body = (
      <div className="cr-error" role="alert">
        <p>We couldn’t load the contact requests. Please try again.</p>
        <Button onClick={() => { setLoad({ state: 'loading' }); setReload((n) => n + 1); }}>Try again</Button>
      </div>
    );
  } else if (load.state === 'loading') {
    body = <p role="status">Loading contact requests…</p>;
  } else if (load.data.counts.all === 0) {
    body = (
      <Card>
        <EmptyState
          icon={icons.message}
          title="No contact requests yet"
          text="When a reader ticks “Contact me about this by email”, they show up here. Everyone else stays anonymous."
        />
      </Card>
    );
  } else {
    const { items, counts } = load.data;
    body = (
      <>
        <div className="cr-filters" role="group" aria-label="Filter by status">
          <ToggleChip selected={!status} onChange={() => pick(null)}>All ({counts.all})</ToggleChip>
          {STATUSES.map((s) => (
            <ToggleChip key={s} selected={status === s} onChange={(on) => pick(on ? s : null)}>
              {STATUS_LABEL[s]} ({counts[s]})
            </ToggleChip>
          ))}
        </div>
        <Card>
          <Table
            caption="Contact requests"
            columns={columns}
            rows={items}
            rowKey={(r) => r.id}
            empty={status ? `No requests marked ${STATUS_LABEL[status].toLowerCase()}.` : 'No requests.'}
          />
        </Card>
      </>
    );
  }

  return (
    <div className="cr-page">
      <PageHeader
        title="Contact requests"
        description="Respondents who ticked “Contact me”. Update the status as you reply."
      />
      {body}
    </div>
  );
}
