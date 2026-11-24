import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { api, type LianaChannel, type LianaConnection, type SyncEvent } from '../../api/client';
import { Button, Card, RadioGroup, Select, Switch, TextField } from '../../components/ui';
import { DEMO_HOST, LIANA_HOST, SEND_OPTIONS, errorText } from './liana';

const STEPS = ['Credentials', 'Test connection', 'Channel', 'What to send', 'Test event'];

type Props = {
  connection: LianaConnection | null;
  demoAvailable: boolean;
  onChange: (connection: LianaConnection) => void;
  onEventSent: () => void;
  onClose: () => void;
};

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section className="wizard-step" aria-labelledby={`wizard-step-${n}`}>
      <h3 id={`wizard-step-${n}`} className="wizard-step-title">
        Step {n} of {STEPS.length}: {title}
      </h3>
      {children}
    </section>
  );
}

/** Connects LianaAutomation in five short steps. Each step saves before the next. */
export function ConnectWizard({ connection, demoAvailable, onChange, onEventSent, onClose }: Props) {
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  // Step 1
  const savedHost = connection?.host;
  const [hostChoice, setHostChoice] = useState(
    savedHost && savedHost !== LIANA_HOST && savedHost !== DEMO_HOST ? 'other' : (savedHost ?? (demoAvailable ? DEMO_HOST : LIANA_HOST)),
  );
  const [otherHost, setOtherHost] = useState(hostChoice === 'other' ? (savedHost ?? '') : '');
  const [clientId, setClientId] = useState(connection?.client_id ?? '');
  const [secret, setSecret] = useState('');
  const host = hostChoice === 'other' ? otherHost : hostChoice;
  const saveCredentials = (e: FormEvent) => {
    e.preventDefault();
    void run(async () => {
      onChange(await api.saveLianaCredentials({ host, client_id: clientId, ...(secret ? { client_secret: secret } : {}) }));
      setSecret('');
      setStep(2);
    });
  };

  // Step 2
  const [tested, setTested] = useState<LianaConnection | null>(null);
  const test = () =>
    run(async () => {
      const result = await api.testLianaConnection();
      setTested(result);
      onChange(result);
    });

  // Step 3
  const [channels, setChannels] = useState<LianaChannel[] | null>(null);
  const [channelId, setChannelId] = useState(connection?.channel_id ?? '');
  const [newName, setNewName] = useState('Survey tool (test)');
  useEffect(() => {
    if (step !== 3 || channels) return;
    void run(async () => setChannels(await api.lianaChannels()));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);
  const createChannel = () =>
    run(async () => {
      const made = await api.createLianaChannel(newName.trim());
      setChannels((list) => [...(list ?? []), made]);
      setChannelId(made.id);
    });
  const chooseChannel = () =>
    run(async () => {
      const chosen = channels?.find((c) => c.id === channelId);
      onChange(await api.changeLianaConnection({ channel_id: channelId, channel_name: chosen?.name ?? channelId }));
      setStep(4);
    });

  // Step 4
  const [settings, setSettings] = useState(connection?.settings ?? { answers: true, contact_requests: true, themes: false });
  const saveSettings = () =>
    run(async () => {
      onChange(await api.changeLianaConnection({ settings }));
      setStep(5);
    });

  // Step 5
  const [email, setEmail] = useState('survey-test-1@example.com');
  const [sent, setSent] = useState<SyncEvent | null>(null);
  const sendTest = () =>
    run(async () => {
      setSent(await api.sendLianaTestEvent(email));
      onEventSent();
    });

  return (
    <Card padded className="wizard">
      <div className="wizard-head">
        <h2 className="integrations-card-title">Connect LianaAutomation</h2>
        <Button size="sm" variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>
      <ol className="wizard-steps" aria-label="Steps">
        {STEPS.map((name, i) => (
          <li key={name} className={i + 1 === step ? 'current' : i + 1 < step ? 'done' : undefined} aria-current={i + 1 === step ? 'step' : undefined}>
            <span className="wizard-dot" aria-hidden="true">{i + 1 < step ? '✓' : i + 1}</span>
            {name}
          </li>
        ))}
      </ol>

      {step === 1 ? (
        <Step n={1} title="Credentials">
          <p className="integrations-hint">
            OAuth client credentials (scope <code>automation-api</code>). Liana creates them in LianaAccount or through your
            account manager; they are not under Settings in LianaAutomation.
          </p>
          <form className="wizard-form" onSubmit={saveCredentials}>
            <Select
              label="Host"
              value={hostChoice}
              onChange={(e) => setHostChoice(e.target.value)}
              options={[
                ...(demoAvailable ? [{ value: DEMO_HOST, label: 'Demo (no Liana account needed)' }] : []),
                { value: LIANA_HOST, label: LIANA_HOST },
                { value: 'other', label: 'Other lianacloud.com host' },
              ]}
            />
            {hostChoice === 'other' ? (
              <TextField label="Other host" value={otherHost} onChange={(e) => setOtherHost(e.target.value)} placeholder="xyz.lianacloud.com" required />
            ) : null}
            {hostChoice === DEMO_HOST ? (
              <p className="integrations-hint">
                Demo mode works offline. Use client ID <code>demo-client</code> and secret <code>demo-secret</code>. A test contact with
                “fail” in its address gets an error, so you can try Retry.
              </p>
            ) : null}
            <TextField label="Client ID" value={clientId} onChange={(e) => setClientId(e.target.value)} required autoComplete="off" />
            <TextField
              label="Client secret"
              type="password"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              required={!connection}
              autoComplete="new-password"
              hint={
                connection
                  ? `Saved${connection.secret_hint ? `: ••••${connection.secret_hint}` : ''}. Leave empty to keep it.`
                  : 'Stored encrypted. Only the last 4 characters are shown afterwards.'
              }
            />
            <div className="wizard-actions">
              <Button type="submit" variant="primary" loading={busy}>
                Save and continue
              </Button>
            </div>
          </form>
        </Step>
      ) : null}

      {step === 2 ? (
        <Step n={2} title="Test connection">
          <p className="integrations-hint">Gets a token and calls <code>/pingpong</code> on {connection?.host}.</p>
          {tested?.status === 'connected' ? (
            <p className="wizard-ok" role="status">✓ Connected to LianaAutomation.</p>
          ) : tested?.status === 'error' ? (
            <p className="wizard-error" role="alert">{tested.last_error}</p>
          ) : null}
          <div className="wizard-actions">
            <Button onClick={() => setStep(1)}>Back</Button>
            <Button onClick={test} loading={busy} variant={tested?.status === 'connected' ? 'secondary' : 'primary'}>
              {tested ? 'Test again' : 'Test connection'}
            </Button>
            <Button variant="primary" disabled={tested?.status !== 'connected'} onClick={() => setStep(3)}>
              Next
            </Button>
          </div>
        </Step>
      ) : null}

      {step === 3 ? (
        <Step n={3} title="Channel">
          <p className="integrations-hint">
            Every event names a channel, so Liana knows where the data came from. Create one called “Survey tool (test)”
            while you test.
          </p>
          {channels === null ? (
            <p role="status">{busy ? 'Loading channels…' : null}</p>
          ) : channels.length > 0 ? (
            <RadioGroup
              legend="Channels in this account"
              name="channel"
              value={channelId}
              onChange={setChannelId}
              options={channels.map((c) => ({ value: c.id, label: c.name, hint: `ID ${c.id}` }))}
            />
          ) : (
            <p className="integrations-hint">This account has no channels yet.</p>
          )}
          <div className="wizard-inline">
            <TextField label="New channel" value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={100} />
            <Button onClick={createChannel} disabled={!newName.trim() || busy}>
              Create channel
            </Button>
          </div>
          <div className="wizard-actions">
            <Button onClick={() => setStep(2)}>Back</Button>
            <Button variant="primary" disabled={!channelId} loading={busy} onClick={chooseChannel}>
              Use this channel
            </Button>
          </div>
        </Step>
      ) : null}

      {step === 4 ? (
        <Step n={4} title="What to send">
          <p className="integrations-hint">
            Only identified answers can be sent: Liana needs a contact. Anonymous answers always stay in the survey tool.
          </p>
          <div className="wizard-switches">
            {SEND_OPTIONS.map((o) => (
              <Switch
                key={o.key}
                label={o.label}
                description={o.description}
                checked={settings[o.key]}
                onChange={(checked) => setSettings((s) => ({ ...s, [o.key]: checked }))}
              />
            ))}
          </div>
          <div className="wizard-actions">
            <Button onClick={() => setStep(3)}>Back</Button>
            <Button variant="primary" loading={busy} onClick={saveSettings}>
              Save and continue
            </Button>
          </div>
        </Step>
      ) : null}

      {step === 5 ? (
        <Step n={5} title="Test event">
          <p className="integrations-hint">
            Sends one <code>survey_answered</code> event (score 3, detractor) for a made-up contact. Use @example.com
            addresses only, never a real person’s.
          </p>
          <div className="wizard-inline">
            <TextField label="Test contact" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Button variant="primary" loading={busy} onClick={sendTest}>
              Send test event
            </Button>
          </div>
          {sent?.status === 'sent' ? (
            <p className="wizard-ok" role="status">
              ✓ Sent. In LianaAutomation, open Contacts and search for {email}: the event is on its timeline. If it is
              missing, look in Settings → Errors.
            </p>
          ) : sent ? (
            <p className="wizard-error" role="alert">
              Not sent: {sent.last_error} It is in the sync log below, where you can retry it.
            </p>
          ) : null}
          <div className="wizard-actions">
            <Button onClick={() => setStep(4)}>Back</Button>
            <Button variant="primary" onClick={onClose}>
              Finish
            </Button>
          </div>
        </Step>
      ) : null}

      {error ? (
        <p className="wizard-error" role="alert">
          {error}
        </p>
      ) : null}
    </Card>
  );
}
