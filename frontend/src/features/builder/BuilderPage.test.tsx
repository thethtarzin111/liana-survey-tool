import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { Survey } from '../../api/client';
import { ToastProvider } from '../../components/ui';
import { BuilderPage } from './BuilderPage';

const saved: Survey = {
  id: 'survey-1',
  title: 'Member survey',
  description: "Members' view of 2026",
  type: 'nps',
  status: 'draft',
};
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset().mockResolvedValue(Response.json(saved));
  // The question list has its own tests (QuestionList.test.tsx); here it just loads empty.
  vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) =>
    String(input).includes('/questions') ? Promise.resolve(Response.json([])) : fetchMock(input, init));
});
afterEach(() => vi.unstubAllGlobals());

function Location() {
  return <span aria-label="Current location">{useLocation().pathname}</span>;
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/surveys/survey-1']}>
      <ToastProvider>
        <Location />
        <Routes>
          <Route path="/surveys/:id" element={<BuilderPage />} />
          <Route path="/surveys/new" element={<h1>Choose a survey type</h1>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

test('loads the survey and fills the title and description fields', async () => {
  renderPage();
  expect(await screen.findByLabelText(/^Survey title/)).toHaveValue('Member survey');
  expect(screen.getByLabelText('Description (optional)')).toHaveValue("Members' view of 2026");
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/surveys/survey-1', {
    headers: { Accept: 'application/json' },
  });
});

test('an empty title blocks saving and announces the field error', async () => {
  renderPage();
  const title = await screen.findByLabelText(/^Survey title/);
  fireEvent.change(title, { target: { value: '   ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Give your survey a title');
  expect(title).toHaveAttribute('aria-invalid', 'true');
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test('saves only changed fields, refreshes values and shows the toast', async () => {
  fetchMock
    .mockResolvedValueOnce(Response.json(saved))
    .mockResolvedValueOnce(Response.json({ ...saved, title: 'Updated survey', description: 'New context' }));
  renderPage();
  fireEvent.change(await screen.findByLabelText(/^Survey title/), { target: { value: 'Updated survey' } });
  fireEvent.change(screen.getByLabelText('Description (optional)'), { target: { value: 'New context' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));

  expect(await screen.findByText('Saved as draft')).toBeInTheDocument();
  expect(fetchMock).toHaveBeenLastCalledWith('/api/v1/surveys/survey-1', {
    method: 'PATCH',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: 'Updated survey', description: 'New context' }),
  });
});

test('omits unchanged fields from the PATCH body', async () => {
  fetchMock
    .mockResolvedValueOnce(Response.json(saved))
    .mockResolvedValueOnce(Response.json({ ...saved, title: 'Title only' }));
  renderPage();
  fireEvent.change(await screen.findByLabelText(/^Survey title/), { target: { value: 'Title only' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
  await screen.findByText('Saved as draft');
  expect(fetchMock).toHaveBeenLastCalledWith('/api/v1/surveys/survey-1', expect.objectContaining({
    body: JSON.stringify({ title: 'Title only' }),
  }));
});

test.each([
  ['Survey title', 'x'.repeat(201), '200 characters'],
  ['Description (optional)', 'x'.repeat(1001), '1000 characters'],
])('blocks an over-limit %s and announces its limit', async (label, value, message) => {
  renderPage();
  fireEvent.change(await screen.findByLabelText(new RegExp(`^${label.replace(/[()]/g, '\\$&')}`)), {
    target: { value },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
  expect(screen.getByRole('alert')).toHaveTextContent(message);
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test('cancel returns to the type picker without saving', async () => {
  renderPage();
  fireEvent.change(await screen.findByLabelText(/^Survey title/), { target: { value: 'Not saved' } });
  fireEvent.click(screen.getByRole('link', { name: 'Cancel' }));
  expect(screen.getByRole('heading', { name: 'Choose a survey type' })).toBeInTheDocument();
  expect(screen.getByLabelText('Current location')).toHaveTextContent('/surveys/new');
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test('shows API validation next to the matching field', async () => {
  fetchMock
    .mockResolvedValueOnce(Response.json(saved))
    .mockResolvedValueOnce(Response.json({
      detail: [{ loc: ['body', 'description'], msg: 'String should have at most 1000 characters' }],
    }, { status: 422 }));
  renderPage();
  fireEvent.change(await screen.findByLabelText('Description (optional)'), {
    target: { value: 'Changed description' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('at most 1000 characters');
  expect(screen.getByLabelText('Description (optional)')).toHaveAttribute('aria-invalid', 'true');
});

test('shows Survey not found and a link back for a missing id', async () => {
  fetchMock.mockResolvedValueOnce(Response.json({ detail: 'Survey not found' }, { status: 404 }));
  renderPage();
  expect(await screen.findByRole('alert')).toHaveTextContent('Survey not found');
  expect(screen.getByRole('link', { name: 'Back to create survey' })).toHaveAttribute('href', '/surveys/new');
});

test('shows a spinner and prevents duplicate saves while PATCH is pending', async () => {
  let complete!: (response: Response) => void;
  fetchMock
    .mockResolvedValueOnce(Response.json(saved))
    .mockImplementationOnce(() => new Promise((resolve) => { complete = resolve; }));
  renderPage();
  fireEvent.change(await screen.findByLabelText(/^Survey title/), { target: { value: 'Updated' } });
  const button = screen.getByRole('button', { name: 'Save as draft' });
  fireEvent.click(button);
  fireEvent.click(button);
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute('aria-busy', 'true');
  expect(fetchMock).toHaveBeenCalledTimes(2);
  complete(Response.json({ ...saved, title: 'Updated' }));
  await waitFor(() => expect(button).toBeEnabled());
});
