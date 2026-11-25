import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { SurveyListItem } from '../../api/client';
import { DEFAULT_ACCENT, DEFAULT_BACKGROUND } from '../builder/branding';
import { writeFlag } from '../settings/featureFlags';
import { FrontPage } from './FrontPage';

function survey(overrides: Partial<SurveyListItem>): SurveyListItem {
  return {
    id: 's1',
    title: 'Member pulse',
    description: null,
    thank_you: null,
    type: 'nps',
    status: 'live',
    opens_at: null,
    closes_at: null,
    answers: 0,
    last_answer_at: null,
    created_at: '2026-11-01T09:00:00Z',
    updated_at: '2026-11-01T09:00:00Z',
    headline: null,
    comment_field: true,
    show_results: true,
    contact_opt_in: true,
    accent_color: DEFAULT_ACCENT,
    background_color: DEFAULT_BACKGROUND,
    logo_url: null,
    ...overrides,
  };
}

function renderPage(surveys: unknown) {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json(surveys)));
  return render(
    <MemoryRouter>
      <FrontPage />
    </MemoryRouter>,
  );
}
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

const region = (name: string) => screen.getByRole('region', { name });

test('a new account sees getting started above an empty dashboard', async () => {
  renderPage([]);
  const start = await screen.findByRole('region', { name: 'Get started with LianaSurvey' });
  expect(within(start).getByText('Create your first survey')).toBeInTheDocument();
  expect(within(start).getByRole('link', { name: 'Create survey' })).toHaveAttribute('href', '/surveys/new');
  expect(within(start).getByRole('link', { name: 'See sharing options' })).toHaveAttribute('href', '/integrations');

  const stats = region('Overall statistics');
  expect(within(stats).getByText('Member NPS').parentElement).toHaveTextContent('— no answers yet');
  expect(within(region('Latest results')).getByText('No results yet')).toBeInTheDocument();
  const yours = region('Your surveys');
  expect(within(yours).getByText('No surveys yet')).toBeInTheDocument();
  expect(within(yours).getByRole('link', { name: 'Browse templates' })).toHaveAttribute('href', '/templates');
});

test('getting started ticks the steps a user has done until answers arrive', async () => {
  renderPage([survey({ status: 'live' })]);
  const start = await screen.findByRole('region', { name: 'Get started with LianaSurvey' });
  expect(within(start).getByText('Create your first survey').closest('li')).toHaveClass('done');
  expect(within(start).getByText('Send it to respondents').closest('li')).toHaveClass('done');
  expect(within(start).getByText('Watch the answers come in').closest('li')).not.toHaveClass('done');
});

test('latest results show the split, the score and a link to that survey', async () => {
  renderPage([
    survey({
      answers: 4,
      headline: { score: 'NPS +25', note: 'scale −100 to +100' },
      answer_counts: { '3': 1, '8': 1, '9': 1, '10': 1 },
      closes_at: '2026-12-31T12:00:00Z',
    }),
  ]);
  const latest = await screen.findByRole('region', { name: 'Latest results' });
  expect(screen.queryByRole('region', { name: 'Get started with LianaSurvey' })).not.toBeInTheDocument();
  expect(within(latest).getByText('NPS survey · 4 answers · Live')).toBeInTheDocument();
  expect(within(latest).getByRole('img', { name: 'Detractors: 25%, Passives: 25%, Promoters: 50%' })).toBeInTheDocument();
  expect(within(latest).getByText('NPS +25')).toBeInTheDocument();
  expect(within(latest).getByRole('link', { name: 'See results' })).toHaveAttribute('href', '/results?survey=s1');
  expect(within(region('Overall statistics')).getByText('Member NPS').parentElement).toHaveTextContent('+25');
});

test('View responses opens the Responses tab of Results', async () => {
  renderPage([survey({ answers: 3 })]);
  const stats = await screen.findByRole('region', { name: 'Overall statistics' });
  expect(within(stats).getByRole('link', { name: 'View responses' })).toHaveAttribute('href', '/results?tab=responses');
});

test('a thumbs score splits into the number and its label', async () => {
  renderPage([survey({ type: 'thumbs', answers: 5, headline: { score: '80% positive', note: '' } })]);
  const latest = await screen.findByRole('region', { name: 'Latest results' });
  expect(within(latest).getByText('80%')).toBeInTheDocument();
  expect(within(latest).getByText('positive')).toBeInTheDocument();
});

test('totals count every survey while lists stay short', async () => {
  renderPage(Array.from({ length: 6 }, (_, i) => survey({ id: `s${i}`, title: `Survey ${i}`, answers: 2 })));
  const stats = await screen.findByRole('region', { name: 'Overall statistics' });
  expect(within(stats).getByText('Responses').parentElement).toHaveTextContent('12');
  expect(within(stats).getByText('Live surveys').parentElement).toHaveTextContent('6');
  expect(within(region('Latest results')).getAllByRole('link', { name: 'See results' })).toHaveLength(3);
  expect(within(region('Your surveys')).getAllByRole('link', { name: 'Open' })).toHaveLength(4);
});

test('the surveys table says when each survey closes', async () => {
  renderPage([
    survey({ id: 'a', title: 'Open ended', status: 'live' }),
    survey({ id: 'b', title: 'Ends soon', status: 'live', closes_at: '2026-11-30T12:00:00Z' }),
    survey({ id: 'c', title: 'Later', status: 'scheduled', opens_at: '2026-12-01T12:00:00Z' }),
    survey({ id: 'd', title: 'Unfinished', status: 'draft' }),
  ]);
  const table = await screen.findByRole('table', { name: 'Your surveys' });
  const row = (title: string) => within(table).getByText(title).closest('tr') as HTMLElement;
  expect(row('Open ended')).toHaveTextContent('No end date');
  expect(row('Ends soon')).toHaveTextContent('Mon 30/11/2026');
  expect(row('Later')).toHaveTextContent('Opens Tue 01/12/2026');
  expect(row('Unfinished')).toHaveTextContent('Not set');
  expect(within(row('Open ended')).getByRole('link', { name: 'Open' })).toHaveAttribute('href', '/surveys/a/live');
});

test('news and inspiration are hidden by default (#153)', async () => {
  renderPage([]);
  expect(await screen.findByRole('heading', { name: 'Get started with LianaSurvey' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'News and inspiration' })).not.toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Recent news' })).not.toBeInTheDocument();
});

test('news and inspiration are hidden when the browser blocks storage', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new DOMException('blocked', 'SecurityError');
  });
  renderPage([]);
  expect(await screen.findByRole('heading', { name: 'Get started with LianaSurvey' })).toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Recent news' })).not.toBeInTheDocument();
});

test('news and inspiration list the articles when the flag is on', async () => {
  writeFlag('newsAndInspiration', true);
  renderPage([]);
  expect(await screen.findByRole('heading', { name: 'News and inspiration' })).toBeInTheDocument();
  const news = await screen.findByRole('region', { name: 'Recent news' });
  expect(within(news).getAllByRole('listitem')).toHaveLength(4);
  expect(within(news).getByRole('link', { name: 'View all ↗' })).toBeInTheDocument();
  expect(within(region('Get inspired')).getByText(/Close the loop with LianaAutomation/)).toBeInTheDocument();
});

test('a failed load shows a retry message', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('nope', { status: 500 })));
  render(
    <MemoryRouter>
      <FrontPage />
    </MemoryRouter>,
  );
  expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t load your dashboard.');
});
