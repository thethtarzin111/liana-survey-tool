import { act, fireEvent, render, screen } from '@testing-library/react';
import { MailerSnippetCard } from './MailerSnippetCard';

const fetchMock = vi.fn<typeof fetch>();
const writeText = vi.fn<(text: string) => Promise<void>>();

function snippetFor(url: string) {
  const query = new URL(url, 'http://localhost').searchParams;
  const campaign = query.get('campaign') ?? 'member-nps-2026';
  const segment = query.get('segment') ?? 'all';
  return { campaign, segment, html: `<a href="...&c=${campaign}&seg=${segment}">9</a>` };
}

beforeEach(() => {
  fetchMock.mockReset().mockImplementation(async (input) => Response.json(snippetFor(String(input))));
  vi.stubGlobal('fetch', fetchMock);
  writeText.mockReset().mockResolvedValue();
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const snippetCalls = () => fetchMock.mock.calls.map(([url]) => String(url));

test('starts with the API default campaign and shows the snippet', async () => {
  render(<MailerSnippetCard surveyId="nps-1" />);
  expect(await screen.findByText('<a href="...&c=member-nps-2026&seg=all">9</a>')).toBeInTheDocument();
  expect(screen.getByLabelText('Campaign tag')).toHaveValue('member-nps-2026');
  expect(screen.getByLabelText('Segment tag')).toHaveValue('all');
  expect(snippetCalls()).toEqual(['/api/v1/surveys/nps-1/snippet?segment=all']);
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST' });
  // Filling in the default campaign does not ask for the same snippet again.
  await act(() => new Promise((resolve) => setTimeout(resolve, 500)));
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test('a new segment tag makes a new snippet after a pause in typing', async () => {
  render(<MailerSnippetCard surveyId="nps-1" />);
  await screen.findByText(/seg=all/);
  vi.useFakeTimers();
  fireEvent.change(screen.getByLabelText('Segment tag'), { target: { value: 'member' } });
  fireEvent.change(screen.getByLabelText('Segment tag'), { target: { value: 'members' } });
  // The old snippet is not offered while its tags no longer match the fields.
  expect(screen.getByRole('button', { name: 'Copy snippet' })).toBeDisabled();
  await act(async () => { await vi.advanceTimersByTimeAsync(400); });
  vi.useRealTimers();
  expect(await screen.findByText(/seg=members/)).toBeInTheDocument();
  expect(snippetCalls()).toEqual([
    '/api/v1/surveys/nps-1/snippet?segment=all',
    '/api/v1/surveys/nps-1/snippet?campaign=member-nps-2026&segment=members',
  ]);
});

test('a tag that is not a slug shows an error and makes no request', async () => {
  render(<MailerSnippetCard surveyId="nps-1" />);
  await screen.findByText(/seg=all/);
  fireEvent.change(screen.getByLabelText('Campaign tag'), { target: { value: 'Spring Campaign' } });
  expect(await screen.findByText(/Use 1–40 lower-case letters/)).toBeInTheDocument();
  expect(screen.getByLabelText('Campaign tag')).toHaveAttribute('aria-invalid', 'true');
  fireEvent.change(screen.getByLabelText('Segment tag'), { target: { value: '' } });
  expect(screen.getByText('Enter a segment tag.')).toBeInTheDocument();
  await act(() => new Promise((resolve) => setTimeout(resolve, 500)));
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test('the reserved segment names show an error and make no request', async () => {
  render(<MailerSnippetCard surveyId="nps-1" />);
  await screen.findByText(/seg=all/);
  for (const name of ['none', 'other']) {
    fireEvent.change(screen.getByLabelText('Segment tag'), { target: { value: name } });
    expect(screen.getByText('This name is reserved. Pick another segment name.')).toBeInTheDocument();
    expect(screen.getByLabelText('Segment tag')).toHaveAttribute('aria-invalid', 'true');
  }
  await act(() => new Promise((resolve) => setTimeout(resolve, 500)));
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test('Copy puts the snippet HTML on the clipboard and confirms it', async () => {
  render(<MailerSnippetCard surveyId="nps-1" />);
  await screen.findByText(/seg=all/);
  fireEvent.click(screen.getByRole('button', { name: 'Copy snippet' }));
  expect(await screen.findByText('Snippet copied. Paste it into an HTML block in LianaMailer.')).toBeInTheDocument();
  expect(writeText).toHaveBeenCalledWith('<a href="...&c=member-nps-2026&seg=all">9</a>');
  expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument();
});

test('shows the steps for pasting into LianaMailer', async () => {
  render(<MailerSnippetCard surveyId="nps-1" />);
  expect(screen.getByRole('heading', { name: 'Paste it into LianaMailer' })).toBeInTheDocument();
  expect(screen.getAllByRole('listitem').map((item) => item.textContent)).toEqual([
    'Open your newsletter in LianaMailer.',
    'Add an HTML block where you want the question, usually at the bottom.',
    'Paste the snippet and send a test email to yourself.',
    'Tap an answer to check that the thank-you page opens.',
  ]);
  await screen.findByText(/seg=all/);
});

test('a survey without a snippet only shows the reason', async () => {
  fetchMock.mockResolvedValue(Response.json({ detail: 'Custom surveys can’t be answered from an email yet.' }, { status: 409 }));
  render(<MailerSnippetCard surveyId="custom-1" />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Custom surveys can’t be answered from an email yet.');
  expect(screen.queryByLabelText('Campaign tag')).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Paste it into LianaMailer' })).not.toBeInTheDocument();
});
