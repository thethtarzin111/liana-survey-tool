import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { SurveyListItem } from '../../api/client';
import { Sidebar } from '../../app/Sidebar';
import { ToastProvider } from '../../components/ui';
import { SurveysPage } from './SurveysPage';
import { DEFAULT_ACCENT, DEFAULT_BACKGROUND } from '../builder/branding';

const base = { description: null, thank_you: null, comment_field: true, show_results: true, contact_opt_in: true, accent_color: DEFAULT_ACCENT, background_color: DEFAULT_BACKGROUND, logo_url: null, opens_at: null, closes_at: null, answers: 0, headline: null } as const;
const live: SurveyListItem = {
  ...base, id: 'live-1', title: 'Member NPS 2026', type: 'nps', status: 'live', answers: 132,
  headline: { score: 'NPS +42', note: 'scale −100 to +100' },
};
const draft: SurveyListItem = { ...base, id: 'draft-1', title: 'Course feedback', type: 'csat', status: 'draft' };
const scheduled: SurveyListItem = {
  ...base, id: 'sched-1', title: 'Newsletter thumbs', type: 'thumbs', status: 'scheduled',
  opens_at: '2026-12-01T09:00:00',
};

const fetchMock = vi.fn<typeof fetch>();
let rows: SurveyListItem[];

function url(input: RequestInfo | URL): URL {
  return new URL(String(input), 'http://localhost');
}

beforeEach(() => {
  rows = [live, scheduled, draft];
  fetchMock.mockReset().mockImplementation(async (input, init) => {
    const { pathname, searchParams } = url(input);
    if (pathname === '/api/v1/me') return Response.json({ tenant_name: 'Example Members Association' });
    if (init?.method === 'DELETE') {
      rows = rows.filter((r) => !pathname.endsWith(r.id));
      return new Response(null, { status: 204 });
    }
    if (init?.method === 'POST') {
      const [, , , , id, action] = pathname.split('/');
      rows = rows.map((r) => (r.id === id ? { ...r, status: action === 'close' ? 'closed' : 'draft' } : r));
      return Response.json(rows.find((r) => r.id === id));
    }
    const q = searchParams.get('q')?.toLowerCase();
    const status = searchParams.get('status');
    return Response.json(
      rows.filter((r) => (!q || r.title.toLowerCase().includes(q)) && (!status || r.status === status)),
    );
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function Location() {
  const { pathname, search } = useLocation();
  return <span aria-label="Current location">{pathname + search}</span>;
}

function renderPage(path = '/surveys') {
  render(
    <MemoryRouter initialEntries={[path]}>
      <ToastProvider>
        <Location />
        <Sidebar />
        <Routes>
          <Route path="/surveys" element={<SurveysPage />} />
          <Route path="/surveys/:id" element={<h1>Builder</h1>} />
          <Route path="/surveys/:id/live" element={<h1>Live page</h1>} />
          <Route path="/surveys/new" element={<h1>New survey</h1>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

function listCalls() {
  return fetchMock.mock.calls.map(([input]) => url(input)).filter((u) => u.pathname === '/api/v1/surveys');
}

async function rowFor(title: string) {
  const link = await screen.findByRole('link', { name: title });
  return link.closest('tr') as HTMLElement;
}

async function openMenu(title: string) {
  fireEvent.click(within(await rowFor(title)).getByRole('button', { name: `Actions for ${title}` }));
}

test('shows each survey with its type, status, answers, note and score', async () => {
  renderPage();
  expect(await screen.findByText('All surveys for Example Members Association.')).toBeInTheDocument();
  const row = await rowFor('Member NPS 2026');
  expect(within(row).getByText('Tag member-nps-2026')).toBeInTheDocument();
  expect(within(row).getByText('NPS survey')).toBeInTheDocument();
  expect(within(row).getByText('Live')).toBeInTheDocument();
  expect(within(row).getByText('132')).toBeInTheDocument();
  expect(within(row).getByText('NPS +42')).toBeInTheDocument();
  expect(within(row).getByText('scale −100 to +100')).toBeInTheDocument();
  expect(within(await rowFor('Course feedback')).getByText('—')).toBeInTheDocument();
  expect(within(await rowFor('Newsletter thumbs')).getByText('Opens Tue 01/12/2026')).toBeInTheDocument();
  expect(within(await rowFor('Course feedback')).getByText('Not published yet')).toBeInTheDocument();
  // Live surveys open their "is live" page (#117).
  expect(screen.getByRole('link', { name: 'Member NPS 2026' })).toHaveAttribute('href', '/surveys/live-1/live');
});

test('status chips filter through the API and keep the choice in the URL', async () => {
  renderPage();
  await rowFor('Member NPS 2026');
  const chips = screen.getByRole('group', { name: 'Filter by status' });
  expect(within(chips).getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true');

  fireEvent.click(within(chips).getByRole('button', { name: 'Draft' }));
  await waitFor(() => expect(screen.queryByRole('link', { name: 'Member NPS 2026' })).not.toBeInTheDocument());
  expect(screen.getByRole('link', { name: 'Course feedback' })).toBeInTheDocument();
  expect(listCalls().at(-1)?.searchParams.get('status')).toBe('draft');
  expect(screen.getByLabelText('Current location')).toHaveTextContent('/surveys?status=draft');
});

test('sidebar search opens the list filtered by the text and Clear search resets it', async () => {
  renderPage('/surveys/new');
  const box = screen.getByRole('searchbox', { name: 'Search surveys' });
  fireEvent.change(box, { target: { value: '  course  ' } });
  fireEvent.keyDown(box, { key: 'Enter' });

  expect(await screen.findByRole('link', { name: 'Course feedback' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Member NPS 2026' })).not.toBeInTheDocument();
  expect(screen.getByText(/Showing surveys matching “course”\./)).toBeInTheDocument();
  expect(listCalls().at(-1)?.searchParams.get('q')).toBe('course');

  fireEvent.click(screen.getByRole('button', { name: 'Clear search' }));
  expect(await screen.findByRole('link', { name: 'Member NPS 2026' })).toBeInTheDocument();
  expect(box).toHaveValue('');
  expect(screen.getByLabelText('Current location')).toHaveTextContent(/^\/surveys$/);
});

test('shows the no-match message when filters find nothing', async () => {
  renderPage('/surveys?q=nothing');
  expect(await screen.findByText('No surveys match. Try another filter or search.')).toBeInTheDocument();
});

test('shows the empty state with Create survey when there are no surveys', async () => {
  rows = [];
  renderPage();
  expect(await screen.findByText('No surveys yet.')).toBeInTheDocument();
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
  expect(screen.getAllByRole('link', { name: /Create survey/ }).length).toBeGreaterThan(1);
});

test('menus offer only the actions the status allows', async () => {
  renderPage();
  const items = async (title: string) => {
    await openMenu(title);
    return within(await rowFor(title)).getAllByRole('menuitem').map((item) => item.textContent);
  };
  expect(await items('Member NPS 2026')).toEqual(['Edit', 'Unpublish', 'Close survey', 'Delete']);
  expect(await items('Newsletter thumbs')).toEqual(['Edit', 'Unpublish', 'Delete']);
  expect(await items('Course feedback')).toEqual(['Edit', 'Publish', 'Delete']);
});

test('close and unpublish call the API, toast and refresh the row', async () => {
  renderPage();
  await openMenu('Member NPS 2026');
  fireEvent.click(screen.getByRole('menuitem', { name: 'Close survey' }));
  expect(await screen.findByText('“Member NPS 2026” is closed. It no longer takes answers.')).toBeInTheDocument();
  expect(within(await rowFor('Member NPS 2026')).getByText('Closed')).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/surveys/live-1/close', expect.objectContaining({ method: 'POST' }));

  await openMenu('Newsletter thumbs');
  fireEvent.click(screen.getByRole('menuitem', { name: 'Unpublish' }));
  expect(await screen.findByText('“Newsletter thumbs” is unpublished. It is now a draft.')).toBeInTheDocument();
  await waitFor(async () => expect(within(await rowFor('Newsletter thumbs')).getByText('Draft')).toBeInTheDocument());
});

test('delete asks first, mentions the answers, and can be cancelled', async () => {
  renderPage();
  await openMenu('Member NPS 2026');
  fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Delete “Member NPS 2026”?' });
  expect(dialog).toHaveTextContent(
    'The survey and its 132 answers will be deleted. This cannot be undone. To keep the results, close the survey instead.',
  );
  fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false);

  await openMenu('Course feedback');
  fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
  const second = screen.getByRole('alertdialog');
  expect(second).toHaveTextContent('The survey will be deleted. This cannot be undone.');
  fireEvent.click(within(second).getByRole('button', { name: 'Delete survey' }));
  expect(await screen.findByText('“Course feedback” was deleted.')).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByRole('link', { name: 'Course feedback' })).not.toBeInTheDocument());
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
});

test('a failed action shows an error toast and keeps the survey', async () => {
  renderPage();
  await rowFor('Member NPS 2026');
  fetchMock.mockResolvedValueOnce(new Response('{"detail":"A draft survey cannot be closed."}', { status: 409 }));
  await openMenu('Member NPS 2026');
  fireEvent.click(screen.getByRole('menuitem', { name: 'Close survey' }));
  expect(await screen.findByText('We couldn’t close “Member NPS 2026”. Please try again.')).toBeInTheDocument();
  expect(within(await rowFor('Member NPS 2026')).getByText('Live')).toBeInTheDocument();
});

test('a failed load can be retried', async () => {
  fetchMock.mockImplementationOnce(async () => new Response('', { status: 500 }));
  fetchMock.mockImplementationOnce(async () => new Response('', { status: 500 }));
  renderPage();
  expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t load your surveys.');
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByRole('link', { name: 'Member NPS 2026' })).toBeInTheDocument();
});

test('a draft is published from its menu, then its live page opens (#117)', async () => {
  renderPage();
  await openMenu('Course feedback');
  fireEvent.click(screen.getByRole('menuitem', { name: 'Publish' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Publish “Course feedback”?' });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Publish' }));
  expect(await screen.findByRole('heading', { name: 'Live page' })).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/surveys/draft-1/publish', expect.objectContaining({ method: 'POST' }));
  expect(screen.getByLabelText('Current location')).toHaveTextContent('/surveys/draft-1/live');
  expect(await screen.findByText('“Course feedback” is live.')).toBeInTheDocument();
});

test('a draft that is not ready keeps the dialog open with the reason', async () => {
  const listOnly = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(async (input, init) => {
    if (init?.method === 'POST' && String(input).endsWith('/publish')) {
      return Response.json({ detail: 'Add the survey’s main question before publishing.' }, { status: 409 });
    }
    return listOnly(input, init);
  });
  renderPage();
  await openMenu('Course feedback');
  fireEvent.click(screen.getByRole('menuitem', { name: 'Publish' }));
  fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Publish' }));
  expect(await screen.findByText('Add the survey’s main question before publishing.')).toBeInTheDocument();
  expect(screen.getByRole('alertdialog')).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Live page' })).not.toBeInTheDocument();
});

test('Edit in the menu opens the editor, also for live surveys', async () => {
  renderPage();
  await openMenu('Member NPS 2026');
  fireEvent.click(screen.getByRole('menuitem', { name: 'Edit' }));
  expect(await screen.findByRole('heading', { name: 'Builder' })).toBeInTheDocument();
  expect(screen.getByLabelText('Current location')).toHaveTextContent('/surveys/live-1');
});
