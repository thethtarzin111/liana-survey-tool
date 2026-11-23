import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { ContactRequest, ContactRequestStatus } from '../../api/client';
import { ToastProvider } from '../../components/ui';
import { ContactRequestsPage } from './ContactRequestsPage';

function request(id: string, extra: Partial<ContactRequest> = {}): ContactRequest {
  return {
    id,
    survey_id: 'survey-1',
    survey_title: 'Member satisfaction 2026',
    survey_type: 'nps',
    contact_ref: `member-${id}`,
    answer: 3,
    reason: 'Price; Service',
    segment: 'members',
    status: 'new',
    liana_status: 'sent',
    created_at: new Date().toISOString(),
    reply_status: null,
    reply_text: null,
    resolved_at: null,
    ...extra,
  };
}

let rows: ContactRequest[];
const fetchMock = vi.fn<typeof fetch>();

function listResponse(status: string | null) {
  const count = (s: ContactRequestStatus) => rows.filter((r) => r.status === s).length;
  return Response.json({
    items: rows.filter((r) => !status || r.status === status),
    counts: { all: rows.length, new: count('new'), contacted: count('contacted'), done: count('done') },
  });
}

beforeEach(() => {
  rows = [
    request('1'),
    request('2', { survey_type: 'thumbs', answer: 0, reason: null, status: 'contacted', liana_status: 'failed' }),
    request('3', { survey_type: 'csat', answer: 2, status: 'done', liana_status: 'pending' }),
  ];
  fetchMock.mockReset().mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost');
    if (init?.method === 'PATCH') {
      const id = url.pathname.split('/').at(-1);
      const row = rows.find((r) => r.id === id)!;
      row.status = JSON.parse(String(init.body)).status;
      return Response.json(row);
    }
    return listResponse(url.searchParams.get('status'));
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function Location() {
  const { search } = useLocation();
  return <span aria-label="Current search">{search}</span>;
}

function renderAt(path = '/contact-requests') {
  render(
    <MemoryRouter initialEntries={[path]}>
      <ToastProvider>
        <Location />
        <Routes>
          <Route path="/contact-requests" element={<ContactRequestsPage />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

const table = () => screen.getByRole('table', { name: 'Contact requests' });
const rowOf = (ref: string) => within(table()).getByText(ref).closest('tr')!;

test('lists each reader by contact reference with their answer, reason, survey and status', async () => {
  renderAt();
  const first = await waitFor(() => rowOf('member-1'));
  expect(within(first).getByText('3')).toBeInTheDocument();
  expect(within(first).getByText('Price; Service')).toBeInTheDocument();
  expect(within(first).getByRole('link', { name: 'Member satisfaction 2026' })).toHaveAttribute(
    'href',
    '/results?survey=survey-1',
  );
  expect(within(first).getByRole('combobox', { name: 'Status for member-1' })).toHaveValue('new');
  expect(within(first).getByText('In LianaAutomation')).toBeInTheDocument();
});

test('reads answers by survey type and shows whether LianaAutomation got the request', async () => {
  renderAt();
  const thumbs = await waitFor(() => rowOf('member-2'));
  expect(within(thumbs).getByText('Not for me')).toBeInTheDocument();
  expect(within(thumbs).getByText('Not sent to LianaAutomation')).toBeInTheDocument();
  const csat = rowOf('member-3');
  expect(within(csat).getByText('2/5')).toBeInTheDocument();
  expect(within(csat).getByText('Sending to LianaAutomation')).toBeInTheDocument();
});

test('filters by status with counts on every chip, and keeps the filter in the address', async () => {
  renderAt();
  const filters = await screen.findByRole('group', { name: 'Filter by status' });
  expect(within(filters).getByRole('button', { name: 'All (3)' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(within(filters).getByRole('button', { name: 'Done (1)' }));
  await waitFor(() => expect(within(table()).queryByText('member-1')).not.toBeInTheDocument());
  expect(within(table()).getByText('member-3')).toBeInTheDocument();
  expect(screen.getByLabelText('Current search')).toHaveTextContent('?status=done');
  expect(String(fetchMock.mock.calls.at(-1)![0])).toBe('/api/v1/contact-requests?status=done');
  // The counts stay for every status while one is picked.
  expect(within(filters).getByRole('button', { name: 'New (1)' })).toBeInTheDocument();
});

test('changing the status saves it and refreshes the counts', async () => {
  renderAt();
  const select = await screen.findByRole('combobox', { name: 'Status for member-1' });
  fireEvent.change(select, { target: { value: 'contacted' } });
  await screen.findByText('member-1: marked as contacted.');
  const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH')!;
  expect(String(patch[0])).toBe('/api/v1/contact-requests/1');
  expect(JSON.parse(String(patch[1]!.body))).toEqual({ status: 'contacted' });
  await screen.findByRole('button', { name: 'Contacted (2)' });
});

test('a status that cannot be saved says so', async () => {
  renderAt();
  const select = await screen.findByRole('combobox', { name: 'Status for member-1' });
  fetchMock.mockImplementationOnce(async () => new Response(null, { status: 500 }));
  fireEvent.change(select, { target: { value: 'done' } });
  await screen.findByText('Could not change the status. Please try again.');
});

test('shows an empty state before anyone asks to be contacted', async () => {
  rows = [];
  renderAt();
  await screen.findByText('No contact requests yet');
  expect(screen.queryByRole('group', { name: 'Filter by status' })).not.toBeInTheDocument();
});

test('says when no request has the picked status', async () => {
  rows = rows.filter((r) => r.status !== 'done');
  renderAt('/contact-requests?status=done');
  await screen.findByText('No requests marked done.');
});

test('offers a retry when the list cannot be loaded', async () => {
  fetchMock.mockImplementationOnce(async () => new Response(null, { status: 500 }));
  renderAt();
  const alert = await screen.findByRole('alert');
  fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
  await waitFor(() => rowOf('member-1'));
});
