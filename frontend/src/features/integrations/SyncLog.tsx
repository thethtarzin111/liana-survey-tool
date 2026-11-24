import { useEffect, useState } from 'react';
import { api, type SyncEvent } from '../../api/client';
import { Badge, Button, Card, Table, ToggleChip, type BadgeTone, type Column } from '../../components/ui';
import { errorText, when } from './liana';

const STATUS: Record<SyncEvent['status'], { label: string; tone: BadgeTone }> = {
  sent: { label: 'Sent', tone: 'positive' },
  pending: { label: 'Waiting', tone: 'neutral' },
  retrying: { label: 'Retrying', tone: 'outline' },
  failed: { label: 'Failed', tone: 'negative' },
  skipped: { label: 'Not sent', tone: 'muted' },
};

/** Every event for LianaAutomation, newest first, with Retry for failed ones. Answers that are
 * deliberately not sent (anonymous, unknown contact) are listed as "Not sent" with the reason. */
export function SyncLog({ reload, onChange }: { reload: number; onChange: () => void }) {
  const [onlyFailed, setOnlyFailed] = useState(false);
  const [rows, setRows] = useState<SyncEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api.syncLog(onlyFailed ? 'failed' : undefined).then(
      (list) => {
        if (active) setRows(list);
      },
      (e: unknown) => {
        if (active) setError(errorText(e));
      },
    );
    return () => {
      active = false;
    };
  }, [onlyFailed, reload]);

  const retry = async (event: SyncEvent) => {
    setRetrying(event.id);
    setError(null);
    try {
      const updated = await api.retrySyncEvent(event.id);
      setRows((list) => (list ?? []).map((row) => (row.id === updated.id ? updated : row)));
      onChange();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setRetrying(null);
    }
  };

  const columns: Column<SyncEvent>[] = [
    { key: 'created_at', header: 'When', render: (e) => when(e.created_at) },
    {
      key: 'verb',
      header: 'Event',
      render: (e) => (
        <>
          <code>{e.verb}</code>
          {e.test ? <span className="sync-test"> test</span> : null}
        </>
      ),
    },
    { key: 'contact', header: 'Contact', render: (e) => e.contact ?? '—' },
    { key: 'status', header: 'Status', render: (e) => <Badge tone={STATUS[e.status].tone}>{STATUS[e.status].label}</Badge> },
    { key: 'attempts', header: 'Tries', numeric: true },
    {
      key: 'last_error',
      header: 'Error or reason',
      render: (e) =>
        e.status === 'skipped' ? (e.last_error ?? '') : <span className="sync-error">{e.last_error ?? ''}</span>,
    },
    {
      key: 'retry',
      header: 'Actions',
      hideHeader: true,
      render: (e) =>
        e.status === 'failed' ? (
          <Button size="sm" loading={retrying === e.id} onClick={() => void retry(e)}>
            Retry
          </Button>
        ) : null,
    },
  ];

  return (
    <Card padded className="integrations-card">
      <div className="integrations-card-head">
        <div>
          <h2 className="integrations-card-title">Sync log</h2>
          <p className="integrations-hint">
            Check that events reached LianaAutomation, and retry the ones that failed. “Not sent” says why an answer
            stayed in the survey tool.
          </p>
        </div>
        <ToggleChip selected={onlyFailed} onChange={setOnlyFailed}>
          Only failed
        </ToggleChip>
      </div>
      {error ? (
        <p className="wizard-error" role="alert">
          {error}
        </p>
      ) : null}
      {rows === null ? (
        <p role="status">Loading the sync log…</p>
      ) : (
        <Table
          caption="Events sent to LianaAutomation"
          columns={columns}
          rows={rows}
          rowKey={(e) => e.id}
          empty={onlyFailed ? 'No failed events.' : 'No events yet. Send a test event to see one here.'}
        />
      )}
    </Card>
  );
}
