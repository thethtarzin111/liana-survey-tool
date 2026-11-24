import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { IntegrationsStatus, LianaConnection, SyncEvent } from '../../api/client';
import { IntegrationsPage } from './IntegrationsPage';

const connection = (overrides: Partial<LianaConnection> = {}): LianaConnection => ({
  host: 'demo', auth_type: 'oauth', client_id: 'demo-client', secret_hint: 'cret', channel_id: null,
  channel_name: null, settings: { answers: true, contact_requests: true, themes: false }, status: 'disconnected',
  last_error: null, updated_at: '2026-11-23T10:00:00Z', ...overrides,
});
const event = (overrides: Partial<SyncEvent> = {}): SyncEvent => ({
  id: 'e1', verb: 'survey_answered', contact: 'su…@example.com', test: true, status: 'sent', attempts: 1,
  last_error: null, created_at: '2026-11-23T10:00:00Z', sent_at: '2026-11-23T10:00:01Z', ...overrides,
});

let status: IntegrationsStatus;
let log: SyncEvent[];
const calls: { method: string; path: string; body: unknown }[] = [];
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  status = { liana_automation: null, events: {}, demo_available: true };
  log = [];
  calls.length = 0;
  fetchMock.mockReset().mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost');
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path: url.pathname + url.search, body });
    const p = url.pathname;
    if (p === '/api/v1/integrations') return Response.json(status);
    if (p.endsWith('/liana-automation') && method === 'PUT') {
      status.liana_automation = connection({ client_id: body.client_id });
      return Response.json(status.liana_automation);
    }
    if (p.endsWith('/liana-automation/test')) {
      status.liana_automation = connection({ ...status.liana_automation, status: 'connected' });
      return Response.json(status.liana_automation);
    }
    if (p.endsWith('/channels') && method === 'GET') return Response.json([{ id: '1', name: 'Website' }]);
    if (p.endsWith('/channels')) return Response.json({ id: '2', name: body.name }, { status: 201 });
    if (p.endsWith('/liana-automation') && method === 'PATCH') {
      status.liana_automation = connection({
        ...status.liana_automation,
        ...(body.channel_id ? { channel_id: body.channel_id, channel_name: body.channel_name } : {}),
        ...(body.settings ? { settings: { ...status.liana_automation!.settings, ...body.settings } } : {}),
      });
      return Response.json(status.liana_automation);
    }
    if (p.endsWith('/test-event')) {
      const sent = event({ id: `e${log.length + 1}` });
      log = [sent, ...log];
      return Response.json(sent, { status: 201 });
    }
    if (p.endsWith('/events')) return Response.json(url.searchParams.get('status') ? log.filter((e) => e.status === 'failed') : log);
    if (p.endsWith('/retry')) {
      const done = event({ id: 'e9', attempts: 2 });
      log = log.map((e) => (e.id === 'e9' ? done : e));
      return Response.json(done);
    }
    if (method === 'DELETE') {
      status.liana_automation = null;
      return new Response(null, { status: 204 });
    }
    return new Response(null, { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const renderPage = () =>
  render(
    <MemoryRouter>
      <IntegrationsPage />
    </MemoryRouter>,
  );
const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }));

test('the wizard connects LianaAutomation step by step', async () => {
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Connect LianaAutomation' }));

  // 1. Credentials, with the demo host offered locally.
  expect(screen.getByLabelText('Host')).toHaveValue('demo');
  fireEvent.change(screen.getByLabelText(/^Client ID/), { target: { value: 'demo-client' } });
  fireEvent.change(screen.getByLabelText(/Client secret/), { target: { value: 'demo-secret' } });
  click('Save and continue');
  expect(await screen.findByRole('heading', { name: 'Step 2 of 5: Test connection' })).toBeInTheDocument();
  expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
    host: 'demo', client_id: 'demo-client', client_secret: 'demo-secret',
  });

  // 2. Test: Next only after a passing test.
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  click('Test connection');
  expect(await screen.findByText('✓ Connected to LianaAutomation.')).toBeInTheDocument();
  click('Next');

  // 3. Channel: create one and use it.
  expect(await screen.findByLabelText(/Website/)).toBeInTheDocument();
  click('Create channel');
  fireEvent.click(await screen.findByLabelText(/Survey tool \(test\)/));
  click('Use this channel');
  expect(await screen.findByRole('heading', { name: 'Step 4 of 5: What to send' })).toBeInTheDocument();
  expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ channel_id: '2', channel_name: 'Survey tool (test)' });

  // 4. What to send.
  fireEvent.click(screen.getByRole('switch', { name: 'Comment themes' }));
  click('Save and continue');
  expect(await screen.findByRole('heading', { name: 'Step 5 of 5: Test event' })).toBeInTheDocument();
  expect(calls.filter((c) => c.method === 'PATCH')[1].body).toEqual({
    settings: { answers: true, contact_requests: true, themes: true },
  });

  // 5. Test event, then the card shows the connection.
  click('Send test event');
  expect(await screen.findByText(/✓ Sent\. In LianaAutomation, open Contacts/)).toBeInTheDocument();
  click('Finish');
  expect(await screen.findByText('Connected')).toBeInTheDocument();
  expect(screen.getByText('••••cret')).toBeInTheDocument();
  expect(screen.getByText('Survey tool (test) (ID 2)')).toBeInTheDocument();
});

test('a failed event can be retried from the sync log', async () => {
  status = { liana_automation: connection({ status: 'connected', channel_id: '1', channel_name: 'Website' }), events: { failed: 1 }, demo_available: true };
  log = [event({ id: 'e9', status: 'failed', last_error: 'Liana answered 503. Try again later.' })];
  renderPage();
  const table = await screen.findByRole('table', { name: 'Events sent to LianaAutomation' });
  expect(within(table).getByText('Failed')).toBeInTheDocument();
  expect(within(table).getByText('Liana answered 503. Try again later.')).toBeInTheDocument();
  fireEvent.click(within(table).getByRole('button', { name: 'Retry' }));
  expect(await within(table).findByText('Sent')).toBeInTheDocument();
  expect(calls.some((c) => c.method === 'POST' && c.path === '/api/v1/integrations/events/e9/retry')).toBe(true);
});

test('an error is shown on the card, and disconnecting asks first', async () => {
  status = {
    liana_automation: connection({ status: 'error', last_error: 'Not found (404): check the host.' }),
    events: {},
    demo_available: false,
  };
  renderPage();
  expect(await screen.findByText('Error')).toBeInTheDocument();
  expect(screen.getByText('Not found (404): check the host.')).toBeInTheDocument();
  click('Disconnect');
  const dialog = screen.getByRole('alertdialog', { name: 'Disconnect LianaAutomation?' });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Disconnect' }));
  expect(await screen.findByRole('button', { name: 'Connect LianaAutomation' })).toBeInTheDocument();
});

test('every way to share a survey is listed with its status (#73)', async () => {
  renderPage();
  for (const [title, badge] of [
    ['LianaMailer', 'Ready'],
    ['Share link and QR code', 'Ready'],
    ['Website embed', 'Planned'],
    ['Export and webhooks', 'Webhooks later'],
  ]) {
    const card = (await screen.findByRole('heading', { name: title })).closest('.integrations-card') as HTMLElement;
    expect(within(card).getByText(badge)).toBeInTheDocument();
  }
});

test('without demo mode only Liana hosts are offered', async () => {
  status = { ...status, demo_available: false };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Connect LianaAutomation' }));
  const host = screen.getByLabelText('Host');
  expect(host).toHaveValue('rest.automation.lianacloud.com');
  expect(within(host).queryByText(/Demo/)).toBeNull();
});
