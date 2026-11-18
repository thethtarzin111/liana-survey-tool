import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import type { SurveyListItem, SurveyOverview } from '../../api/client';
import { ResultsPage } from './ResultsPage';

function listItem(id: string, title: string, overrides: Partial<SurveyListItem> = {}): SurveyListItem {
  return {
    id, title, description: null, thank_you: null, type: 'nps', status: 'live', opens_at: null, closes_at: null,
    answers: 0, last_answer_at: null, headline: null, comment_field: true, show_results: true, contact_opt_in: true,
    accent_color: 'x', background_color: 'y', logo_url: null, ...overrides,
  };
}

function overview(overrides: Partial<SurveyOverview> = {}): SurveyOverview {
  return {
    survey_id: 'nps-1', title: 'Member NPS 2026', type: 'nps', status: 'live', closes_at: null,
    last_answer_at: '2026-11-19T10:00:00Z', channels: ['link'], segment: 'all', segments: [], responses: 12, views: 40,
    response_rate: 30, completed_all: null,
    main: { question_id: 'q1', kind: 'nps', score: -33, change: null, counts: { '3': 5, '8': 3, '10': 4 } },
    questions: [], reasons: [], trend: [], by_segment: [],
    ...overrides,
  };
}

const lists: SurveyListItem[] = [
  listItem('nps-1', 'Member NPS 2026', { answers: 12, last_answer_at: '2026-11-18T10:00:00Z' }),
  listItem('thumbs-1', 'Newsletter thumbs', { type: 'thumbs', answers: 30, last_answer_at: '2026-11-19T08:00:00Z' }),
  listItem('csat-1', 'Course feedback', { type: 'csat', answers: 5, last_answer_at: '2026-11-10T08:00:00Z' }),
  listItem('custom-1', 'Campus survey', { type: 'custom' }),
];
const segments = [
  { value: 'members', label: 'Members', answers: 8 },
  { value: 'guests', label: 'Guests', answers: 6 },
];

const fetchMock = vi.fn<typeof fetch>();
let surveyList: SurveyListItem[];
let overviews: Record<string, SurveyOverview>;
let overviewStatus: number;

beforeEach(() => {
  surveyList = lists;
  overviews = {};
  overviewStatus = 200;
  fetchMock.mockReset().mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost');
    if (url.pathname === '/api/v1/surveys') return Response.json(surveyList);
    const match = /^\/api\/v1\/results\/([^/]+)\/overview$/.exec(url.pathname);
    if (match) {
      if (overviewStatus !== 200) return new Response(null, { status: overviewStatus });
      const base = overviews[match[1]] ?? overview({ survey_id: match[1] });
      return Response.json({ ...base, segment: url.searchParams.get('segment') ?? 'all' });
    }
    return new Response(null, { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function Location() {
  const { pathname, search } = useLocation();
  return <span aria-label="Current location">{pathname + search}</span>;
}

function renderPage(path = '/results') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Location />
      <ResultsPage />
    </MemoryRouter>,
  );
}

const location = () => screen.getByLabelText('Current location').textContent;
const overviewCalls = () =>
  fetchMock.mock.calls
    .map(([input]) => new URL(String(input), 'http://localhost'))
    .filter((u) => u.pathname.endsWith('/overview'))
    .map((u) => `${u.pathname.split('/')[4]}?${u.searchParams.toString()}`);
const pickerButton = () => screen.getByRole('button', { name: /^Survey/ });

test('defaults to the survey in the URL, else the latest answer, else the newest', async () => {
  const { unmount } = renderPage('/results?survey=csat-1');
  await screen.findByRole('tab', { name: /Overview/ });
  expect(pickerButton()).toHaveTextContent('Course feedback');
  expect(overviewCalls()).toEqual(['csat-1?segment=all']);
  unmount();

  fetchMock.mockClear();
  const second = renderPage();
  await screen.findByRole('tab', { name: /Overview/ });
  expect(pickerButton()).toHaveTextContent('Newsletter thumbs');
  expect(overviewCalls()).toEqual(['thumbs-1?segment=all']);
  second.unmount();

  fetchMock.mockClear();
  surveyList = [listItem('new-1', 'Brand new'), listItem('old-1', 'Older')];
  renderPage();
  await screen.findByRole('tab', { name: /Overview/ });
  expect(pickerButton()).toHaveTextContent('Brand new');
  expect(overviewCalls()).toEqual(['new-1?segment=all']);
});

test('tabs and segment live in the URL', async () => {
  overviews['nps-1'] = overview({ segments });
  renderPage('/results?survey=nps-1');
  fireEvent.click(await screen.findByRole('tab', { name: /Responses/ }));
  expect(location()).toBe('/results?survey=nps-1&tab=responses');

  fireEvent.change(screen.getByLabelText('Segment'), { target: { value: 'members' } });
  expect(location()).toBe('/results?survey=nps-1&tab=responses&segment=members');
  await waitFor(() => expect(overviewCalls()).toContain('nps-1?segment=members'));
  expect(screen.getByLabelText('Segment')).toHaveValue('members');

  fireEvent.click(screen.getByRole('tab', { name: /Overview/ }));
  expect(location()).toBe('/results?survey=nps-1&segment=members');
});

test('opening a link with a tab and segment shows that view', async () => {
  overviews['nps-1'] = overview({ segments });
  renderPage('/results?survey=nps-1&tab=responses&segment=guests');
  expect(await screen.findByRole('tab', { name: /Responses/ })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByLabelText('Segment')).toHaveValue('guests');
});

test('picking another survey resets the segment', async () => {
  overviews['nps-1'] = overview({ segments });
  renderPage('/results?survey=nps-1&segment=members');
  await screen.findByRole('tab', { name: /Overview/ });
  fireEvent.click(pickerButton());
  fireEvent.click(screen.getByRole('option', { name: /Course feedback/ }));
  expect(location()).toBe('/results?survey=csat-1');
  await waitFor(() => expect(overviewCalls()).toContain('csat-1?segment=all'));
});

test('a segment the API refuses falls back to all segments', async () => {
  fetchMock.mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost');
    if (url.pathname === '/api/v1/surveys') return Response.json(lists);
    if (url.searchParams.get('segment') !== 'all') return new Response(null, { status: 400 });
    return Response.json(overview());
  });
  renderPage('/results?survey=nps-1&segment=gone');
  await screen.findByRole('tab', { name: /Overview/ });
  expect(location()).toBe('/results?survey=nps-1');
});

test.each([[[]], [segments.slice(0, 1)]])('segment filter hidden with fewer than 2 segments (%j)', async (few) => {
  overviews['nps-1'] = overview({ segments: few });
  renderPage('/results?survey=nps-1');
  await screen.findByRole('tab', { name: /Overview/ });
  expect(screen.queryByLabelText('Segment')).not.toBeInTheDocument();
});

test('segment filter lists all segments and the answers of each', async () => {
  overviews['nps-1'] = overview({ segments });
  renderPage('/results?survey=nps-1');
  const select = await screen.findByLabelText('Segment');
  expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual([
    'All segments',
    'Members (8)',
    'Guests (6)',
  ]);
});

test('the status line tells state, last answer, close date and channels', async () => {
  overviews['nps-1'] = overview({
    last_answer_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
    closes_at: '2026-12-31T12:00:00',
    channels: ['email', 'link', 'qr'],
  });
  renderPage('/results?survey=nps-1');
  const line = await screen.findByTestId('status-line');
  expect(line).toHaveTextContent(
    'Collecting answers · last one 2 h ago · Closes Thu 31/12/2026 · Sent by email, shared by link, QR code',
  );
});

test('the status line of a closed survey without answers', async () => {
  overviews['nps-1'] = overview({ status: 'closed', last_answer_at: null, channels: [], responses: 0 });
  renderPage('/results?survey=nps-1');
  expect(await screen.findByTestId('status-line')).toHaveTextContent('Closed · no answers yet');
});

describe('KPI cards per survey type', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-19T12:00:00'));
  });
  afterEach(() => vi.useRealTimers());
  const kpi = (label: string) => within(screen.getByRole('list')).getByText(label).closest('li') as HTMLElement;

  test('NPS', async () => {
    overviews['nps-1'] = overview({
      main: { question_id: 'q1', kind: 'nps', score: -33, change: -5, counts: { '3': 5, '8': 3, '10': 4 } },
    });
    renderPage('/results?survey=nps-1');
    await screen.findByText('Promoters');
    expect(kpi('NPS')).toHaveTextContent('−33');
    expect(kpi('NPS')).toHaveTextContent('−5 since October');
    expect(kpi('Responses')).toHaveTextContent('12');
    expect(kpi('Responses')).toHaveTextContent('all segments');
    expect(kpi('Response rate')).toHaveTextContent('30%');
    expect(kpi('Response rate')).toHaveTextContent('12 of 40 viewed');
    expect(kpi('Promoters')).toHaveTextContent('33%');
    expect(kpi('Promoters')).toHaveTextContent('vs 42% detractors');
  });

  test('NPS with a positive score is signed', async () => {
    overviews['nps-1'] = overview({
      main: { question_id: 'q1', kind: 'nps', score: 40, change: 5, counts: {} },
    });
    renderPage('/results?survey=nps-1');
    await screen.findByText('Promoters');
    expect(kpi('NPS')).toHaveTextContent('+40');
    expect(kpi('NPS')).toHaveTextContent('+5 since October');
  });

  test('thumbs', async () => {
    overviews['thumbs-1'] = overview({
      survey_id: 'thumbs-1', type: 'thumbs', responses: 10,
      main: { question_id: 'q1', kind: 'thumbs', score: 80, change: null, counts: { '0': 2, '1': 5, '2': 3 } },
    });
    renderPage('/results?survey=thumbs-1');
    await screen.findByText('Positive (Good + Loved it)');
    expect(kpi('Positive (Good + Loved it)')).toHaveTextContent('80%');
    expect(kpi('Loved it')).toHaveTextContent('30%');
    expect(kpi('Loved it')).toHaveTextContent('3 answers');
  });

  test('CSAT', async () => {
    overviews['csat-1'] = overview({
      survey_id: 'csat-1', type: 'csat',
      main: { question_id: 'q1', kind: 'rating', score: 75, change: null, counts: { '1': 1, '3': 2, '4': 3, '5': 6 } },
      questions: [{ id: 'q1', kind: 'rating', prompt: 'How was it?', required: true, answers: 12, options: [], average: 4.2 }],
    });
    renderPage('/results?survey=csat-1');
    await screen.findByText('Satisfied (4–5)');
    expect(kpi('Satisfied (4–5)')).toHaveTextContent('75%');
    expect(kpi('Average rating')).toHaveTextContent('4.2');
    expect(kpi('Average rating')).toHaveTextContent('out of 5');
  });

  test('custom', async () => {
    overviews['custom-1'] = overview({
      survey_id: 'custom-1', type: 'custom', completed_all: 64, main: null,
      questions: [
        { id: 'a', kind: 'text', prompt: 'Why?', required: false, answers: 5, options: [], average: null },
        { id: 'b', kind: 'rating', prompt: 'Ease of finding info', required: true, answers: 12, options: [], average: 3.8 },
      ],
    });
    renderPage('/results?survey=custom-1');
    await screen.findByText('Completed all questions');
    expect(screen.queryByText('NPS')).not.toBeInTheDocument();
    expect(kpi('Completed all questions')).toHaveTextContent('64%');
    expect(kpi('Completed all questions')).toHaveTextContent('the rest skipped optional ones');
    expect(kpi('Average rating')).toHaveTextContent('3.8');
    expect(kpi('Average rating')).toHaveTextContent('Ease of finding info');
  });

  test('custom without a rating question has no average card', async () => {
    overviews['custom-1'] = overview({ survey_id: 'custom-1', type: 'custom', completed_all: 64, main: null });
    renderPage('/results?survey=custom-1');
    await screen.findByText('Completed all questions');
    expect(screen.queryByText('Average rating')).not.toBeInTheDocument();
  });
});

test('response rate shows "—" and "Not available per segment" with a segment', async () => {
  overviews['nps-1'] = overview({ segments, response_rate: null });
  renderPage('/results?survey=nps-1&segment=members');
  await screen.findByText('Promoters');
  const card = screen.getByText('Response rate').closest('li') as HTMLElement;
  expect(card).toHaveTextContent('—');
  expect(card).toHaveTextContent('Not available per segment');
  expect(within(screen.getByRole('list')).getByText('Responses').closest('li')).toHaveTextContent('segment: Members');
});

test('response rate without views shows "—"', async () => {
  overviews['nps-1'] = overview({ views: 0, response_rate: null });
  renderPage('/results?survey=nps-1');
  await screen.findByText('Promoters');
  expect(screen.getByText('Response rate').closest('li')).toHaveTextContent('—No views yet');
});

test('overview without answers shows empty states', async () => {
  overviews['nps-1'] = overview({
    responses: 0, last_answer_at: null, response_rate: null, views: 0,
    main: { question_id: 'q1', kind: 'nps', score: null, change: null, counts: {} },
  });
  renderPage('/results?survey=nps-1');
  expect(await screen.findByText('No answers yet')).toBeInTheDocument();
  expect(screen.queryByText('Promoters')).not.toBeInTheDocument();
  expect(screen.getByRole('tab', { name: 'Responses 0' })).toBeInTheDocument();
});

test('no surveys at all shows an empty state with a way to start', async () => {
  surveyList = [];
  renderPage();
  expect(await screen.findByText('No surveys yet')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Create survey' })).toHaveAttribute('href', '/surveys/new');
});

test('unknown survey shows "Survey not found" and the picker', async () => {
  renderPage('/results?survey=gone');
  expect(await screen.findByText('Survey not found')).toBeInTheDocument();
  expect(overviewCalls()).toEqual([]);
  fireEvent.click(screen.getByRole('button', { name: /^Survey/ }));
  fireEvent.click(screen.getByRole('option', { name: /Course feedback/ }));
  expect(location()).toBe('/results?survey=csat-1');
  expect(await screen.findByRole('tab', { name: /Overview/ })).toBeInTheDocument();
});

test('a survey deleted since the list loaded shows "Survey not found"', async () => {
  overviewStatus = 404;
  renderPage('/results?survey=nps-1');
  expect(await screen.findByText('Survey not found')).toBeInTheDocument();
});

test('a failed load offers to try again', async () => {
  overviewStatus = 500;
  renderPage('/results?survey=nps-1');
  expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t load these results.');
  overviewStatus = 200;
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByRole('tab', { name: /Overview/ })).toBeInTheDocument();
});

test('a failed survey list offers to try again', async () => {
  fetchMock.mockImplementation(async () => new Response(null, { status: 500 }));
  renderPage();
  expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t load your surveys.');
});

test('the Responses tab shows the number of responses', async () => {
  renderPage('/results?survey=nps-1&tab=responses');
  expect(await screen.findByRole('tab', { name: 'Responses 12' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByText('Responses will appear here soon.')).toBeInTheDocument();
});
