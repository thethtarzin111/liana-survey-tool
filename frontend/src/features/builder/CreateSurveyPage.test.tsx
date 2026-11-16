import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { Survey } from '../../api/client';
import { ToastProvider } from '../../components/ui';
import { BuilderPage } from './BuilderPage';
import { CreateSurveyPage } from './CreateSurveyPage';

const draft: Survey = {
  id: 'saved-survey', title: 'Untitled survey', description: null, type: 'nps', status: 'draft',
};
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  let saved = draft;
  fetchMock.mockReset().mockImplementation(async (_path, init) => {
    if (init?.method === 'POST') saved = { ...draft, ...JSON.parse(init.body as string) };
    return Response.json(saved);
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function Location() {
  return <span aria-label="Current location">{useLocation().pathname}</span>;
}

function renderPage(path = '/surveys/new') {
  render(
    <MemoryRouter initialEntries={[path]}>
      <ToastProvider>
        <Location />
        <Link to="/surveys">Leave creation</Link>
        <Routes>
          <Route path="/surveys/new" element={<CreateSurveyPage />} />
          <Route path="/surveys/:id" element={<BuilderPage />} />
          <Route path="/surveys" element={<h1>Surveys</h1>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

test('shows four type cards with use cases without creating a survey', () => {
  renderPage();
  const cards = within(screen.getByRole('region', { name: 'Survey types' })).getAllByRole('button');
  expect(cards).toHaveLength(4);
  for (const card of cards) expect(within(card).getByText('Use this when')).toBeInTheDocument();
  expect(screen.getByText(/One tap: Not for me, Good, Loved it/)).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});

test.each([
  ['Thumbs rating', 'thumbs'], ['NPS survey (0–10)', 'nps'],
  ['CSAT survey (1–5)', 'csat'], ['Start from scratch', 'custom'],
])('choosing %s saves the right type and opens the persisted draft', async (label, type) => {
  renderPage();
  fireEvent.click(screen.getByRole('button', { name: new RegExp(`^${label.replace(/[()]/g, '\\$&')}`) }));
  expect(await screen.findByLabelText(/^Survey title/)).toHaveValue('Untitled survey');
  expect(screen.getByRole('heading', { name: 'Build your survey' })).toBeInTheDocument();
  expect(screen.getByLabelText('Current location')).toHaveTextContent('/surveys/saved-survey');
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/surveys', {
    method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ type }),
  });
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/surveys/saved-survey', expect.anything());
});

test('disables every card while saving and prevents duplicate requests', async () => {
  let complete!: (response: Response) => void;
  fetchMock.mockImplementationOnce(() => new Promise((resolve) => { complete = resolve; }));
  renderPage();
  const card = screen.getByRole('button', { name: /^Thumbs rating/ });
  fireEvent.click(card);
  fireEvent.click(card);
  for (const button of within(screen.getByRole('region')).getAllByRole('button')) {
    expect(button).toBeDisabled();
  }
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(screen.getByText('Saving your draft…')).toBeInTheDocument();
  complete(Response.json(draft));
  expect(await screen.findByLabelText(/^Survey title/)).toHaveValue('Untitled survey');
});

test.each(['server', 'network'])('shows page and toast errors after a %s failure and allows retry', async (failure) => {
  if (failure === 'server') fetchMock.mockResolvedValueOnce(new Response('Internal error', { status: 500 }));
  else fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
  renderPage();
  fireEvent.click(screen.getByRole('button', { name: /^NPS survey/ }));
  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent('We couldn’t save your draft. Please try again.');
  expect(within(screen.getByRole('status')).getByText(alert.textContent!)).toBeInTheDocument();
  expect(screen.getByLabelText('Current location')).toHaveTextContent('/surveys/new');
  const retry = screen.getByRole('button', { name: /^NPS survey/ });
  expect(retry).toBeEnabled();
  fireEvent.click(retry);
  expect(await screen.findByLabelText(/^Survey title/)).toHaveValue('Untitled survey');
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(2);
});

test('cancel returns to Surveys without saving', () => {
  renderPage();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(screen.getByRole('heading', { name: 'Surveys' })).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});

test('a completed save does not take the user back after they navigate away', async () => {
  let complete!: (response: Response) => void;
  fetchMock.mockImplementationOnce(() => new Promise((resolve) => { complete = resolve; }));
  renderPage();
  fireEvent.click(screen.getByRole('button', { name: /^NPS survey/ }));
  fireEvent.click(screen.getByRole('link', { name: 'Leave creation' }));
  complete(Response.json(draft));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  expect(screen.getByLabelText('Current location')).toHaveTextContent('/surveys');
  expect(screen.getByRole('heading', { name: 'Surveys' })).toBeInTheDocument();
  expect(screen.queryByText('Draft saved')).not.toBeInTheDocument();
});

test('a draft URL loads the saved survey and can recover from a load failure', async () => {
  fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
  renderPage('/surveys/saved-survey');
  expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t load this survey.');
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(await screen.findByLabelText(/^Survey title/)).toHaveValue('Untitled survey');
});
