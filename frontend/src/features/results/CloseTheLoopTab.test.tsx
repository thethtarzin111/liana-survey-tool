import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ContactRequest } from '../../api/client';
import { ToastProvider } from '../../components/ui';
import { CloseTheLoopTab } from './CloseTheLoopTab';

function request(id: string, extra: Partial<ContactRequest> = {}): ContactRequest {
  return {
    id,
    survey_id: 'survey-1',
    survey_title: 'Member satisfaction 2026',
    survey_type: 'nps',
    contact_ref: `member-${id}`,
    answer: 4,
    reason: 'Events',
    segment: 'members',
    status: 'new',
    liana_status: 'sent',
    created_at: '2026-11-20T10:00:00Z',
    reply_status: null,
    reply_text: null,
    resolved_at: null,
    ...extra,
  };
}

let rows: ContactRequest[];
let resolveStatus = 200;
const fetchMock = vi.fn<typeof fetch>();
const SAID_DID = 'You said the events start too late. From January they start at 17.';

beforeEach(() => {
  resolveStatus = 200;
  rows = [request('1')];
  fetchMock.mockReset().mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost');
    const parts = url.pathname.split('/');
    if (init?.method === 'PATCH') {
      const row = rows.find((r) => r.id === parts.at(-1))!;
      row.status = JSON.parse(String(init.body)).status;
      return Response.json(row);
    }
    if (init?.method === 'POST') {
      if (resolveStatus !== 200) return Response.json({ detail: 'nope' }, { status: resolveStatus });
      const row = rows.find((r) => r.id === parts.at(-2))!;
      Object.assign(row, { status: 'done', reply_status: 'pending', reply_text: JSON.parse(String(init.body)).message });
      return Response.json(row);
    }
    return Response.json({ items: rows, counts: { all: rows.length, new: 0, contacted: 0, done: 0 } });
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderTab(segment = 'all') {
  render(
    <MemoryRouter>
      <ToastProvider>
        <CloseTheLoopTab surveyId="survey-1" segment={segment} />
      </ToastProvider>
    </MemoryRouter>,
  );
}

const rowOf = (ref: string) =>
  within(screen.getByRole('table', { name: 'Readers to follow up' })).getByText(ref).closest('tr')!;

test('lists the survey’s readers who asked to be contacted', async () => {
  renderTab();
  const row = await waitFor(() => rowOf('member-1'));
  expect(String(fetchMock.mock.calls[0][0])).toBe('/api/v1/contact-requests?survey_id=survey-1');
  expect(within(row).getByText('Events')).toBeInTheDocument();
  expect(within(row).getByText('members')).toBeInTheDocument();
  expect(within(row).getByText('In LianaAutomation')).toBeInTheDocument();
});

test('a reader is contacted, then resolved with a “You said, we did” message', async () => {
  renderTab();
  fireEvent.click(await screen.findByRole('button', { name: 'Mark as contacted' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Mark resolved' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Resolve and tell the reader' });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Send and resolve' }));
  expect(within(dialog).getByText('Write what changed, so the reader hears back.')).toBeInTheDocument();
  fireEvent.change(within(dialog).getByLabelText('“You said, we did” message'), { target: { value: `  ${SAID_DID} ` } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Send and resolve' }));
  await screen.findByText('Resolved · telling the reader…');
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')!;
  expect(String(post[0])).toBe('/api/v1/contact-requests/1/resolve');
  expect(JSON.parse(String(post[1]!.body))).toEqual({ message: SAID_DID });
});

test('shows when the reader has been told, and offers to send a failed message again', async () => {
  rows = [
    request('1', { status: 'done', reply_status: 'sent', reply_text: SAID_DID }),
    request('2', { status: 'done', reply_status: 'failed', reply_text: SAID_DID }),
  ];
  renderTab();
  expect(await within(await waitFor(() => rowOf('member-1'))).findByText('✓ Resolved · reader told')).toBeInTheDocument();
  const failed = rowOf('member-2');
  expect(within(failed).getByText('Reader not told')).toBeInTheDocument();
  fireEvent.click(within(failed).getByRole('button', { name: 'Send again' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Send the message again' });
  expect(within(dialog).getByLabelText('“You said, we did” message')).toHaveValue(SAID_DID);
});

test('a message that cannot be queued is reported and the list reloads', async () => {
  rows = [request('1', { status: 'contacted' })];
  resolveStatus = 503;
  renderTab();
  fireEvent.click(await screen.findByRole('button', { name: 'Mark resolved' }));
  const dialog = screen.getByRole('alertdialog');
  fireEvent.change(within(dialog).getByLabelText('“You said, we did” message'), { target: { value: SAID_DID } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Send and resolve' }));
  await screen.findByText('Marked as done, but the message could not be sent. Try again.');
  await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => !init?.method)).toHaveLength(2));
});

test('a request marked done elsewhere can still tell the reader', async () => {
  rows = [request('1', { status: 'done' })];
  renderTab();
  expect(await screen.findByRole('button', { name: 'Tell the reader' })).toBeInTheDocument();
});

test('follows the Results segment filter', async () => {
  rows = [request('1'), request('2', { segment: 'board' })];
  renderTab('board');
  await waitFor(() => rowOf('member-2'));
  expect(screen.queryByText('member-1')).not.toBeInTheDocument();
});

test('says when nobody has asked to be contacted', async () => {
  rows = [];
  renderTab();
  await screen.findByText('Nobody has asked to be contacted yet');
});
