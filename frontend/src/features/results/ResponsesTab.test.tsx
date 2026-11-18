import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import type { ResponseDetail, ResponseRow } from '../../api/client';
import { ResponsesTab } from './ResponsesTab';
import { useResultsParams } from './useResultsParams';

function row(n: number, overrides: Partial<ResponseRow> = {}): ResponseRow {
  return {
    id: `id-${n}`, display_id: `R-${String(1000 + n)}`, submitted_at: '2026-11-19T09:12:00Z', answer: 3,
    reason: 'Too long', comment: `Comment ${n}`, masked: false, segment_label: 'Members', ...overrides,
  };
}
const many = (from: number, count: number) => Array.from({ length: count }, (_, i) => row(from + i));

const detail: ResponseDetail = {
  display_id: 'R-1001', submitted_at: '2026-11-19T09:12:00Z', segment_label: 'Members',
  answers: [
    { question_id: 'q1', prompt: 'How likely are you to recommend us?', kind: 'nps', value: 3, masked: false },
    { question_id: 'q2', prompt: 'What could be better?', kind: 'long_text', value: 'Write to [hidden] please', masked: true },
    { question_id: 'q3', prompt: 'Which topics?', kind: 'multiple_choice', value: ['Events', 'News'], masked: false },
    { question_id: 'q4', prompt: 'Anything else?', kind: 'text', value: null, masked: false },
  ],
};

const fetchMock = vi.fn<typeof fetch>();
let pageRows: ResponseRow[];
let total: number;

beforeEach(() => {
  pageRows = [row(1), row(2)];
  total = 2;
  fetchMock.mockReset().mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost');
    if (/\/responses\/[^/]+$/.test(url.pathname)) return Response.json(detail);
    if (url.pathname.endsWith('/responses')) {
      const offset = Number(url.searchParams.get('offset') ?? 0);
      const rows = offset ? many(offset + 1, 3) : pageRows;
      return Response.json({ total, rows });
    }
    return new Response(null, { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const lastCall = () => new URL(String(fetchMock.mock.calls.at(-1)?.[0]), 'http://localhost');

function Location() {
  const l = useLocation();
  return <output data-testid="loc">{l.pathname + l.search}</output>;
}
const location = () => screen.getByTestId('loc').textContent;

function Tab({ scale = 'nps' as 'nps' | 'thumbs' | 'rating' | null }) {
  const { segment } = useResultsParams();
  return <ResponsesTab surveyId="s1" segment={segment} scale={scale} />;
}
function renderTab(url = '/results?survey=s1&tab=responses', scale: 'nps' | 'thumbs' | 'rating' | null = 'nps') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Tab scale={scale} />
      <Location />
    </MemoryRouter>,
  );
}

test('rows newest first with ID, Received, Answer, Reason, Comment, Segment', async () => {
  pageRows = [row(2, { answer: 9, reason: 'Fast' }), row(1, { segment_label: null })];
  renderTab();
  const table = await screen.findByRole('table');
  const heads = within(table).getAllByRole('columnheader').map((h) => h.textContent);
  expect(heads).toEqual(['ID', 'Received', 'Answer', 'Reason', 'Comment', 'Segment']);
  const rows = within(table).getAllByRole('row').slice(1);
  expect(rows[0]).toHaveTextContent('R-1002');
  expect(rows[0]).toHaveTextContent('9');
  expect(rows[0]).toHaveTextContent('Fast');
  expect(rows[0]).toHaveTextContent('Comment 2');
  expect(rows[0]).toHaveTextContent('Members');
  expect(rows[1]).toHaveTextContent('R-1001');
  expect(within(rows[1]).getAllByText('—').length).toBeGreaterThan(0);
  expect(screen.getByText('Showing 2 of 2 responses, newest first')).toBeInTheDocument();
  expect(lastCall().searchParams.get('limit')).toBe('50');
});

test('masked comment shows "Personal details hidden"', async () => {
  pageRows = [row(1, { comment: 'Call me on [hidden]', masked: true }), row(2)];
  renderTab();
  expect(await screen.findByText('Personal details hidden')).toBeInTheDocument();
  expect(screen.getByText('Call me on [hidden]')).toBeInTheDocument();
  expect(screen.getAllByText('Personal details hidden')).toHaveLength(1);
});

test('search and group chips filter and update the URL', async () => {
  renderTab('/results?survey=s1&tab=responses&segment=members');
  await screen.findByRole('table');
  fireEvent.change(screen.getByRole('searchbox', { name: 'Search comments' }), { target: { value: 'slow' } });
  fireEvent.keyDown(screen.getByRole('searchbox', { name: 'Search comments' }), { key: 'Enter' });
  await waitFor(() => expect(location()).toBe('/results?survey=s1&tab=responses&segment=members&q=slow'));
  await waitFor(() => expect(lastCall().searchParams.get('q')).toBe('slow'));
  expect(lastCall().searchParams.get('segment')).toBe('members');

  fireEvent.click(screen.getByRole('button', { name: 'Detractors' }));
  await waitFor(() => expect(location()).toContain('group=detractors'));
  await waitFor(() => expect(lastCall().searchParams.get('group')).toBe('detractors'));
  expect(screen.getByRole('button', { name: 'Detractors' })).toHaveAttribute('aria-pressed', 'true');

  fireEvent.click(screen.getByRole('button', { name: 'All answers' }));
  await waitFor(() => expect(location()).not.toContain('group='));
});

test('chips per survey type', async () => {
  const names = () => screen.getAllByRole('button', { pressed: false }).concat(screen.queryAllByRole('button', { pressed: true })).map((b) => b.textContent);
  const { unmount } = renderTab('/results?survey=s1&tab=responses', 'nps');
  await screen.findByRole('table');
  expect(names()).toEqual(expect.arrayContaining(['All answers', 'Detractors', 'Passives', 'Promoters']));
  unmount();
  const second = renderTab('/results?survey=s1&tab=responses', 'thumbs');
  await screen.findByRole('table');
  expect(names()).toEqual(expect.arrayContaining(['Not for me', 'Good', 'Loved it']));
  second.unmount();
  const third = renderTab('/results?survey=s1&tab=responses', 'rating');
  await screen.findByRole('table');
  expect(names()).toEqual(expect.arrayContaining(['1–2', '3', '4–5']));
  third.unmount();
  renderTab('/results?survey=s1&tab=responses', null);
  await screen.findByRole('table');
  expect(screen.queryByRole('button', { name: 'All answers' })).not.toBeInTheDocument();
});

test('Load more appends the next 50', async () => {
  pageRows = many(1, 50);
  total = 53;
  renderTab();
  await screen.findByText('Showing 50 of 53 responses, newest first');
  fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
  await screen.findByText('R-1051');
  expect(lastCall().searchParams.get('offset')).toBe('50');
  expect(screen.getByText('R-1001')).toBeInTheDocument();
  expect(screen.getByText('Showing 53 of 53 responses, newest first')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
});

test('"No responses yet" and "No responses match." with "Clear filters"', async () => {
  pageRows = [];
  total = 0;
  const { unmount } = renderTab();
  expect(await screen.findByText('No responses yet')).toBeInTheDocument();
  unmount();
  renderTab('/results?survey=s1&tab=responses&q=zzz&group=promoters');
  expect(await screen.findByText('No responses match.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
  await waitFor(() => expect(location()).toBe('/results?survey=s1&tab=responses'));
});

test('row click opens every answer in a side panel, Escape closes and returns focus', async () => {
  renderTab();
  const first = (await screen.findAllByRole('row'))[1];
  const trigger = within(first).getByRole('button', { name: /R-1001/ });
  trigger.focus();
  fireEvent.click(first);
  const dialog = await screen.findByRole('dialog', { name: /R-1001/ });
  expect(dialog).toHaveAttribute('aria-modal', 'true');
  expect(await within(dialog).findByText('How likely are you to recommend us?')).toBeInTheDocument();
  expect(within(dialog).getByText('Write to [hidden] please')).toBeInTheDocument();
  expect(within(dialog).getByText('Personal details hidden')).toBeInTheDocument();
  expect(within(dialog).getByText('Events, News')).toBeInTheDocument();
  expect(within(dialog).getByText('No answer')).toBeInTheDocument();
  expect(dialog.contains(document.activeElement)).toBe(true);
  fireEvent.keyDown(dialog, { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(trigger).toHaveFocus();
});

test('Enter on a row button opens the panel', async () => {
  renderTab();
  const trigger = await screen.findByRole('button', { name: /R-1002/ });
  fireEvent.click(trigger);
  expect(await screen.findByRole('dialog')).toBeInTheDocument();
});

test('Export CSV link carries the filters', async () => {
  renderTab('/results?survey=s1&tab=responses&segment=members&q=slow&group=detractors');
  const link = await screen.findByRole('link', { name: 'Export CSV' });
  const url = new URL(link.getAttribute('href') as string, 'http://localhost');
  expect(url.pathname).toBe('/api/v1/results/s1/responses.csv');
  expect(url.searchParams.get('segment')).toBe('members');
  expect(url.searchParams.get('q')).toBe('slow');
  expect(url.searchParams.get('group')).toBe('detractors');
  expect(link).toHaveAttribute('download');
});

test('the anonymised notice links to Contact requests', async () => {
  renderTab();
  expect(await screen.findByText(/Anonymised\. No names or emails are shown\./)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Contact requests' })).toHaveAttribute('href', '/contact-requests');
});
