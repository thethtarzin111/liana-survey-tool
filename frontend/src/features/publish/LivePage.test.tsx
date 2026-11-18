import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Survey } from '../../api/client';
import { DEFAULT_ACCENT, DEFAULT_BACKGROUND } from '../builder/branding';
import { LivePage } from './LivePage';

const PUBLIC = 'http://localhost:8000/r/A8z6rHHXeBX9tLUp2nfrVg';
const survey: Survey = {
  id: 'nps-1', title: 'Member NPS', description: null, thank_you: null, type: 'nps', status: 'live',
  public_url: PUBLIC, published_at: '2026-11-18T09:00:00Z',
  comment_field: true, show_results: true, contact_opt_in: true,
  accent_color: DEFAULT_ACCENT, background_color: DEFAULT_BACKGROUND, logo_url: null,
};
const links = [1, 2, 3].map((n) => `${PUBLIC}?r=test-abc123-${n}&s=sig${n}`);

const fetchMock = vi.fn<typeof fetch>();
let current: Survey;
let testLinks: Response | null;

beforeEach(() => {
  current = survey;
  testLinks = null;
  fetchMock.mockReset().mockImplementation(async (input) => {
    if (String(input).endsWith('/test-links')) return testLinks ?? Response.json({ links });
    return Response.json(current);
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/surveys/nps-1/live']}>
      <Routes>
        <Route path="/surveys/:id/live" element={<LivePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

test('shows the survey is live with its public link', async () => {
  renderPage();
  expect(await screen.findByRole('heading', { name: 'Member NPS is live' })).toBeInTheDocument();
  expect(screen.getByLabelText('Public link')).toHaveValue(`${PUBLIC}?ch=link`);
  expect(screen.getByLabelText('Public link')).toHaveAttribute('readonly');
  expect(screen.getByRole('link', { name: 'Back to surveys' })).toHaveAttribute('href', '/surveys');
  expect(screen.getByRole('link', { name: 'Edit survey' })).toHaveAttribute('href', '/surveys/nps-1');
});

test('in local development, each test reader has one link per answer', async () => {
  renderPage();
  const box = (await screen.findByRole('heading', { name: 'Try it as a reader' })).closest('section') as HTMLElement;
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/surveys/nps-1/test-links', expect.objectContaining({ method: 'POST' }));
  const nine = within(box).getByRole('link', { name: 'Reader 2 answers 9' });
  expect(nine).toHaveAttribute('href', `${links[1]}&a=9`);
  expect(nine).toHaveAttribute('target', '_blank');
  // NPS: 0–10 for each of the 3 readers.
  expect(within(box).getAllByRole('link')).toHaveLength(33);
});

test('thumbs surveys get the three thumbs answers', async () => {
  current = { ...survey, type: 'thumbs' };
  renderPage();
  const loved = await screen.findByRole('link', { name: 'Reader 1 answers Loved it' });
  expect(loved).toHaveAttribute('href', `${links[0]}&a=2`);
});

test('no test-links box where the API has none (outside local development)', async () => {
  testLinks = new Response(null, { status: 404 });
  renderPage();
  expect(await screen.findByRole('heading', { name: 'Member NPS is live' })).toBeInTheDocument();
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(screen.queryByRole('heading', { name: 'Try it as a reader' })).not.toBeInTheDocument();
});

test('a survey that is not live says so and links to the editor', async () => {
  current = { ...survey, status: 'draft', public_url: null };
  renderPage();
  expect(await screen.findByText('“Member NPS” is not live, so it has no working link yet.')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Edit the survey' })).toHaveAttribute('href', '/surveys/nps-1');
});

test('the link is copied with one click and the page says so (#6)', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Copy link' }));
  expect(await screen.findByText('Link copied')).toBeInTheDocument();
  expect(writeText).toHaveBeenCalledWith(`${PUBLIC}?ch=link`);
  expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument();
});

test('when copying is not allowed, the page asks to copy by hand', async () => {
  vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) } });
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Copy link' }));
  expect(await screen.findByText('We couldn’t copy the link. Select it and copy it yourself.')).toBeInTheDocument();
});

test('the QR code of the public link is shown and can be downloaded (#6)', async () => {
  renderPage();
  const image = await screen.findByRole('img', { name: 'QR code for the public link' });
  const data = image.getAttribute('src')!;
  expect(data).toMatch(/^data:image\/png;base64,/);
  const download = screen.getByRole('link', { name: 'Download QR code' });
  expect(download).toHaveAttribute('href', data);
  expect(download).toHaveAttribute('download', 'member-nps-qr.png');
  await act(async () => {});
});
