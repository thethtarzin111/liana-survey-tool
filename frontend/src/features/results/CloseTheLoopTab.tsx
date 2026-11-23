import { useEffect, useState } from 'react';
import { api, ApiError, errorDetail, type ContactRequest } from '../../api/client';
import { Badge, Button, Card, ConfirmDialog, EmptyState, Table, TextArea, icons, useToast, type Column } from '../../components/ui';
import { AnswerBadge, LianaBadge } from '../contact-requests/ContactRequestsPage';

const MAX_MESSAGE = 1000;

type Load = { state: 'loading' } | { state: 'failed' } | { state: 'ready'; rows: ContactRequest[] };

/** The next step for one request, as in the prototype: contact, then resolve and tell the reader. */
function StatusAction({
  row,
  busy,
  onContacted,
  onResolve,
}: {
  row: ContactRequest;
  busy: boolean;
  onContacted: () => void;
  onResolve: () => void;
}) {
  if (row.reply_status === 'sent') return <Badge tone="positive">✓ Resolved · reader told</Badge>;
  if (row.reply_status === 'pending') return <Badge tone="outline">Resolved · telling the reader…</Badge>;
  if (row.reply_status === 'failed') {
    return (
      <div className="loop-action">
        <Badge tone="negative">Reader not told</Badge>
        <Button size="sm" variant="secondary" onClick={onResolve} disabled={busy}>Send again</Button>
      </div>
    );
  }
  if (row.status === 'new') {
    return <Button size="sm" variant="secondary" onClick={onContacted} loading={busy}>Mark as contacted</Button>;
  }
  return (
    <div className="loop-action">
      {row.status === 'contacted' ? <span className="loop-done">✓ Contacted</span> : <span className="loop-done">✓ Done</span>}
      <Button size="sm" variant="primary" onClick={onResolve} disabled={busy}>
        {row.status === 'done' ? 'Tell the reader' : 'Mark resolved'}
      </Button>
    </div>
  );
}

/** Readers of one survey who asked to be contacted, with the steps to close the loop with each. */
export function CloseTheLoopTab({ surveyId, segment }: { surveyId: string; segment: string }) {
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [resolving, setResolving] = useState<ContactRequest | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    let active = true;
    api.contactRequests({ surveyId }).then(
      (data) => { if (active) setLoad({ state: 'ready', rows: data.items }); },
      () => { if (active) setLoad({ state: 'failed' }); },
    );
    return () => { active = false; };
  }, [surveyId, reload]);

  const replace = (row: ContactRequest) =>
    setLoad((prev) => (prev.state === 'ready' ? { ...prev, rows: prev.rows.map((r) => (r.id === row.id ? row : r)) } : prev));

  const markContacted = (row: ContactRequest) => {
    setBusy(row.id);
    api.setContactRequestStatus(row.id, 'contacted').then(
      (saved) => { setBusy(null); replace(saved); },
      () => { setBusy(null); toast('Could not change the status. Please try again.'); },
    );
  };

  const openResolve = (row: ContactRequest) => {
    setResolving(row);
    setMessage(row.reply_text ?? '');
    setError(null);
  };

  const send = () => {
    if (!resolving) return;
    const text = message.trim();
    if (!text) {
      setError('Write what changed, so the reader hears back.');
      return;
    }
    const row = resolving;
    setBusy(row.id);
    api.resolveContactRequest(row.id, text).then(
      (saved) => {
        setBusy(null);
        setResolving(null);
        replace(saved);
        toast(`${row.contact_ref}: resolved. The reader is being told.`);
      },
      (failure: unknown) => {
        setBusy(null);
        if (failure instanceof ApiError && failure.status === 503) {
          setResolving(null);
          setReload((n) => n + 1);
          toast('Marked as done, but the message could not be sent. Try again.');
        } else if (failure instanceof ApiError && failure.status === 409) {
          setResolving(null);
          setReload((n) => n + 1);
          toast('This reader has been told already.');
        } else {
          setError(errorDetail(failure) ?? 'Could not resolve the request. Please try again.');
        }
      },
    );
  };

  const columns: Column<ContactRequest>[] = [
    { key: 'reader', header: 'Reader', render: (r) => <strong>{r.contact_ref}</strong> },
    { key: 'answer', header: 'Answer', render: (r) => <AnswerBadge row={r} /> },
    { key: 'reason', header: 'Reason', render: (r) => r.reason ?? <span className="loop-none">—</span> },
    { key: 'segment', header: 'Segment' },
    { key: 'liana', header: 'LianaAutomation', render: (r) => <LianaBadge status={r.liana_status} /> },
    {
      key: 'status',
      header: 'Status',
      render: (r) => (
        <StatusAction
          row={r}
          busy={busy === r.id}
          onContacted={() => markContacted(r)}
          onResolve={() => openResolve(r)}
        />
      ),
    },
  ];

  const intro = (
    <div className="loop-intro">
      <h2 className="loop-title">Readers to follow up</h2>
      <p className="loop-note">
        Only readers who ticked “Contact me about this by email” appear here. Everyone else stays anonymous. Each request
        goes to LianaAutomation. Marking a request as resolved sends the reader your “You said, we did” message.
      </p>
    </div>
  );

  let body;
  if (load.state === 'failed') {
    body = (
      <Card padded role="alert" className="results-error">
        <strong>We couldn’t load the follow-up list.</strong>
        <Button onClick={() => { setLoad({ state: 'loading' }); setReload((n) => n + 1); }}>Try again</Button>
      </Card>
    );
  } else if (load.state === 'loading') {
    body = <p role="status">Loading the follow-up list…</p>;
  } else {
    const rows = segment === 'all' ? load.rows : load.rows.filter((r) => r.segment === segment);
    body = rows.length ? (
      <Card>
        <Table caption="Readers to follow up" columns={columns} rows={rows} rowKey={(r) => r.id} />
      </Card>
    ) : (
      <Card>
        <EmptyState
          icon={icons.loop}
          title={load.rows.length ? 'Nobody in this segment asked to be contacted' : 'Nobody has asked to be contacted yet'}
          text="Readers who tick “Contact me about this by email” show up here."
        />
      </Card>
    );
  }

  return (
    <div className="loop-tab">
      {intro}
      {body}
      <ConfirmDialog
        open={resolving !== null}
        title={resolving?.reply_status === 'failed' ? 'Send the message again' : 'Resolve and tell the reader'}
        confirmLabel="Send and resolve"
        busy={busy !== null && busy === resolving?.id}
        onConfirm={send}
        onCancel={() => setResolving(null)}
      >
        <p className="loop-dialog-text">
          {resolving?.contact_ref} gets this message through LianaAutomation. The request is marked as done.
        </p>
        <TextArea
          label="“You said, we did” message"
          hint={`What changed because of their feedback. Up to ${MAX_MESSAGE} characters.`}
          rows={5}
          maxLength={MAX_MESSAGE}
          value={message}
          error={error ?? undefined}
          onChange={(e) => { setMessage(e.target.value); setError(null); }}
        />
      </ConfirmDialog>
    </div>
  );
}
