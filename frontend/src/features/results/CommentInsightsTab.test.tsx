import { fireEvent, render, screen, within } from '@testing-library/react';
import type { CommentInsights, InsightTheme } from '../../api/client';
import { CommentInsightsTab } from './CommentInsightsTab';

function theme(overrides: Partial<InsightTheme> = {}): InsightTheme {
  return {
    key: 'price', label: 'Price', outlier: false, comments: 6, percent: 60,
    sentiment: { negative: 4, neutral: 1, positive: 1 }, score: -50, score_vs_all: -40,
    quotes: [{ comment_id: 'C1', text: 'The fee is too high', summary: 'Fee feels high.' }],
    hidden_quotes: 1, samples: ['The fee is too high for what we get', 'Price is fine'],
    ...overrides,
  };
}

function insights(overrides: Partial<CommentInsights> = {}): CommentInsights {
  return {
    survey_id: 's1', status: 'ready', mode: 'direct', kind: 'nps', comments: 10, redacted: 1,
    min_comments: 5, direct_limit: 50, score: -10,
    themes: [
      theme(),
      theme({
        key: 'events', label: 'Events', comments: 3, percent: 30, sentiment: { negative: 0, neutral: 0, positive: 3 },
        score: null, score_vs_all: null, quotes: [], hidden_quotes: 0, samples: ['Great events'],
      }),
      theme({
        key: 'other', label: 'Other', outlier: true, comments: 1, percent: 10,
        sentiment: { negative: 0, neutral: 1, positive: 0 }, score: null, score_vs_all: null, quotes: [],
        hidden_quotes: 0, samples: ['ok'],
      }),
    ],
    negative_themes: [{ key: 'price', label: 'Price', count: 4, percent: 100 }],
    run: { grouper: null, writer: 'Mock (no LLM connected)', llm_calls: 1 },
    ...overrides,
  };
}

const fetchMock = vi.fn<typeof fetch>();
let body: CommentInsights;
beforeEach(() => {
  body = insights();
  fetchMock.mockReset().mockImplementation(async () => Response.json(body));
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const renderTab = (onReadAll = () => {}) =>
  render(<CommentInsightsTab surveyId="s1" segment="members" onReadAll={onReadAll} />);

test('asks for the survey and segment, and shows the numbers from the server', async () => {
  renderTab();
  expect(await screen.findByRole('heading', { name: 'What people talk about' })).toBeInTheDocument();
  expect(String(fetchMock.mock.calls[0][0])).toBe('/api/v1/results/s1/comment-insights?segment=members');
  expect(screen.getByText('AI-generated, editable')).toBeInTheDocument();
  const kpis = within(screen.getByRole('list', { name: 'Summary' }));
  expect(kpis.getByText('Comments analysed').nextSibling).toHaveTextContent('10');
  expect(kpis.getByText('1 with personal data hidden')).toBeInTheDocument();
  expect(kpis.getByText('Themes found').nextSibling).toHaveTextContent('2');
  expect(kpis.getByText('NPS of commenters').nextSibling).toHaveTextContent('−10');
  expect(kpis.getByText('Negative comments').nextSibling).toHaveTextContent('40%');
});

test('the first theme is open with its verified quotes; another can be picked', async () => {
  renderTab();
  const price = await screen.findByRole('button', { name: /^Price/ });
  expect(price).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByRole('heading', { name: 'Price', level: 3 })).toBeInTheDocument();
  expect(screen.getByText(/6 comments · 60% of all 10 · NPS −50 \(−40 vs all commenters\)/)).toBeInTheDocument();
  expect(screen.getByText('The fee is too high')).toBeInTheDocument();
  expect(screen.getByText('1 suggested quote hidden: not found word-for-word in the comments.')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /^Events/ }));
  expect(screen.getByRole('heading', { name: 'Events', level: 3 })).toBeInTheDocument();
  expect(screen.queryByText('The fee is too high')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: /^Other/ }));
  expect(screen.getByText('Not a theme')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Rename' })).toBeNull();
});

test('renaming a theme changes it everywhere and marks it', async () => {
  renderTab();
  fireEvent.click(await screen.findByRole('button', { name: 'Rename' }));
  fireEvent.change(screen.getByLabelText('Theme name'), { target: { value: 'Membership fee' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  expect(screen.getByRole('heading', { name: 'Membership fee', level: 3 })).toBeInTheDocument();
  expect(screen.getByText('Renamed by you')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^Membership fee/ })).toBeInTheDocument();
  const negative = screen.getByText('Themes in negative comments').closest('figure') as HTMLElement;
  expect(within(negative).getByText('Membership fee')).toBeInTheDocument();
});

test('too few comments show a message instead of charts', async () => {
  body = insights({ status: 'too_few', mode: null, comments: 3, themes: [], negative_themes: [] });
  const onReadAll = vi.fn();
  renderTab(onReadAll);
  expect(await screen.findByText('Not enough comments yet')).toBeInTheDocument();
  expect(screen.getByText('Themes show up once the survey has 5 comments. It has 3 so far.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Read the comments' }));
  expect(onReadAll).toHaveBeenCalledOnce();
});

test('a failed request can be retried', async () => {
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 500 }));
  renderTab();
  expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t load the comment insights.');
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByRole('heading', { name: 'What people talk about' })).toBeInTheDocument();
});
