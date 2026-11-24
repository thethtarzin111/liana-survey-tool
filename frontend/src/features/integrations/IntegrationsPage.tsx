import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type IntegrationsStatus, type LianaConnection } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Badge, Button, ButtonLink, Card, ConfirmDialog, Switch, type BadgeTone } from '../../components/ui';
import { ConnectWizard } from './ConnectWizard';
import { SEND_OPTIONS, errorText, when } from './liana';
import { SyncLog } from './SyncLog';
import './integrations.css';

const STATUS: Record<LianaConnection['status'], { label: string; tone: BadgeTone }> = {
  connected: { label: 'Connected', tone: 'positive' },
  disconnected: { label: 'Not tested', tone: 'outline' },
  error: { label: 'Error', tone: 'negative' },
};

function LianaAutomationCard({
  status,
  onEdit,
  onChange,
  onDisconnected,
  onEventSent,
}: {
  status: IntegrationsStatus;
  onEdit: () => void;
  onChange: (c: LianaConnection) => void;
  onDisconnected: () => void;
  onEventSent: () => void;
}) {
  const c = status.liana_automation;
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const act = async (action: () => Promise<void>) => {
    setBusy(true);
    setMessage(null);
    try {
      await action();
    } catch (e) {
      setMessage({ ok: false, text: errorText(e) });
    } finally {
      setBusy(false);
    }
  };

  const head = (
    <div className="integrations-card-head">
      <div>
        <h2 className="integrations-card-title">LianaAutomation</h2>
        <p className="integrations-hint">
          Identified answers and “Contact me” requests become events on the contact, so segments and automations can
          react to them.
        </p>
      </div>
      {c ? <Badge tone={STATUS[c.status].tone}>{STATUS[c.status].label}</Badge> : <Badge tone="muted">Not connected</Badge>}
    </div>
  );

  if (!c) {
    return (
      <Card padded className="integrations-card integrations-main">
        {head}
        <ol className="integrations-flow">
          <li>Answer saved in the survey tool</li>
          <li>Connector sends it with POST /import</li>
          <li>Event on the contact’s timeline in LianaAutomation</li>
          <li>Segments and automations react</li>
        </ol>
        <div>
          <Button variant="primary" onClick={onEdit}>
            Connect LianaAutomation
          </Button>
        </div>
      </Card>
    );
  }

  const sent = status.events.sent ?? 0;
  const failed = status.events.failed ?? 0;
  return (
    <Card padded className="integrations-card integrations-main">
      {head}
      {c.status === 'error' && c.last_error ? (
        <p className="wizard-error" role="alert">
          {c.last_error}
        </p>
      ) : null}
      <dl className="integrations-facts">
        <dt>Host</dt>
        <dd>{c.host === 'demo' ? 'Demo (no Liana account)' : c.host}</dd>
        <dt>Client ID</dt>
        <dd>{c.client_id}</dd>
        <dt>Secret</dt>
        <dd>{c.secret_hint ? `••••${c.secret_hint}` : '••••'}</dd>
        <dt>Channel</dt>
        <dd>{c.channel_id ? `${c.channel_name} (ID ${c.channel_id})` : 'Not chosen yet'}</dd>
        <dt>Events</dt>
        <dd>
          {sent} sent{failed ? `, ${failed} failed` : ''}
        </dd>
        <dt>Changed</dt>
        <dd>{when(c.updated_at)}</dd>
      </dl>
      <div className="integrations-switches">
        {SEND_OPTIONS.map((o) => (
          <Switch
            key={o.key}
            label={o.label}
            description={o.description}
            checked={c.settings[o.key]}
            disabled={busy}
            onChange={(checked) =>
              void act(async () => onChange(await api.changeLianaConnection({ settings: { [o.key]: checked } })))
            }
          />
        ))}
      </div>
      <p className="integrations-hint">
        Sending real answers comes with the next step (the outbox and queue). Today the switches are saved and test
        events can be sent.
      </p>
      {message ? (
        <p className={message.ok ? 'wizard-ok' : 'wizard-error'} role={message.ok ? 'status' : 'alert'}>
          {message.text}
        </p>
      ) : null}
      <div className="integrations-actions">
        <Button
          onClick={() =>
            void act(async () => {
              const result = await api.testLianaConnection();
              onChange(result);
              setMessage(
                result.status === 'connected'
                  ? { ok: true, text: '✓ Connected to LianaAutomation.' }
                  : { ok: false, text: result.last_error ?? 'The test failed.' },
              );
            })
          }
          loading={busy}
        >
          Test connection
        </Button>
        <Button
          disabled={!c.channel_id || busy}
          onClick={() =>
            void act(async () => {
              const event = await api.sendLianaTestEvent();
              onEventSent();
              setMessage(
                event.status === 'sent'
                  ? { ok: true, text: '✓ Test event sent for survey-test-1@example.com. Find it under Contacts in LianaAutomation.' }
                  : { ok: false, text: `Not sent: ${event.last_error}` },
              );
            })
          }
        >
          Send test event
        </Button>
        <Button onClick={onEdit}>Change settings</Button>
        <Button variant="danger" onClick={() => setConfirm(true)}>
          Disconnect
        </Button>
      </div>
      <ConfirmDialog
        open={confirm}
        title="Disconnect LianaAutomation?"
        confirmLabel="Disconnect"
        danger
        busy={busy}
        onCancel={() => setConfirm(false)}
        onConfirm={() =>
          void act(async () => {
            await api.disconnectLiana();
            setConfirm(false);
            onDisconnected();
          })
        }
      >
        The saved credentials and channel are removed and nothing more is sent. The sync log stays.
      </ConfirmDialog>
    </Card>
  );
}

function LianaMailerCard() {
  return (
    <Card padded className="integrations-card">
      <div className="integrations-card-head">
        <h2 className="integrations-card-title">LianaMailer</h2>
        <Badge tone="positive">Ready</Badge>
      </div>
      <p className="integrations-hint">
        Put a survey’s rating block in a newsletter. Each number is a link; LianaMailer fills in every recipient’s
        contact tag when it sends, so answers can be identified without an email address in the link.
      </p>
      <p className="integrations-hint">
        Open a live survey and copy its <strong>newsletter snippet</strong>.
      </p>
      <div>
        <ButtonLink to="/surveys">Choose a survey</ButtonLink>
      </div>
    </Card>
  );
}

function ExportCard() {
  return (
    <Card padded className="integrations-card">
      <div className="integrations-card-head">
        <h2 className="integrations-card-title">Export and webhooks</h2>
        <Badge tone="muted">Webhooks later</Badge>
      </div>
      <p className="integrations-hint">
        Download every response as CSV from <Link to="/results?tab=responses">Results → Responses</Link>. Webhooks, which
        post each answer to your own URL, are planned.
      </p>
    </Card>
  );
}

function LianaSetupCard() {
  return (
    <Card padded className="integrations-card">
      <h2 className="integrations-card-title">Then, in LianaAutomation</h2>
      <p className="integrations-hint">Once events arrive, build these in Liana (no code). Name everything “Survey tool (test)”.</p>
      <ol className="integrations-checklist">
        <li>
          <strong>Segment “Survey detractors”</strong>: Segments → Add new segment, your channel, event{' '}
          <code>survey_answered</code> with <code>nps_group</code> = detractor.
        </li>
        <li>
          <strong>Segment “Survey promoters”</strong>: the same with promoter.
        </li>
        <li>
          <strong>Automation “Detractor alert”</strong>: when a contact enters the detractor segment, email the account
          owner.
        </li>
        <li>
          <strong>Automation “Contact request”</strong>: on <code>survey_contact_request</code>, notify the owner.
        </li>
        <li>
          <strong>Automation “Promoter thank-you”</strong>: a thank-you email with a “recommend us” link.
        </li>
      </ol>
      <p className="integrations-hint">
        If a segment cannot filter on event items, use one verb per group instead (survey_detractor, survey_promoter).
      </p>
    </Card>
  );
}

export function IntegrationsPage() {
  const [status, setStatus] = useState<IntegrationsStatus | null>(null);
  const [failed, setFailed] = useState(false);
  const [wizard, setWizard] = useState(false);
  const [logReload, setLogReload] = useState(0);

  const load = useCallback(() => {
    setFailed(false);
    api.integrations().then(setStatus, () => setFailed(true));
  }, []);
  useEffect(load, [load]);

  const changed = (connection: LianaConnection) => setStatus((s) => (s ? { ...s, liana_automation: connection } : s));
  const eventSent = () => {
    setLogReload((n) => n + 1);
    load();
  };

  const header = (
    <PageHeader title="Integrations" description="Send survey answers to other Liana products, or share them anywhere." />
  );
  if (failed) {
    return (
      <div className="integrations-page">
        {header}
        <Card padded role="alert" className="integrations-error">
          <strong>We couldn’t load your integrations.</strong>
          <Button onClick={load}>Try again</Button>
        </Card>
      </div>
    );
  }
  if (!status) return <p role="status">Loading integrations…</p>;

  return (
    <div className="integrations-page">
      {header}
      {wizard ? (
        <ConnectWizard
          connection={status.liana_automation}
          demoAvailable={status.demo_available}
          onChange={changed}
          onEventSent={eventSent}
          onClose={() => {
            setWizard(false);
            load();
          }}
        />
      ) : (
        <LianaAutomationCard
          status={status}
          onEdit={() => setWizard(true)}
          onChange={changed}
          onDisconnected={load}
          onEventSent={eventSent}
        />
      )}
      <div className="integrations-grid">
        <LianaMailerCard />
        <ExportCard />
      </div>
      <SyncLog reload={logReload} onChange={load} />
      <LianaSetupCard />
    </div>
  );
}
