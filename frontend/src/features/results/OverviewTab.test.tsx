import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { SurveyOverview } from '../../api/client';
import { OverviewTab } from './OverviewTab';

function overview(overrides: Partial<SurveyOverview> = {}): SurveyOverview {
  return {
    survey_id: 's', title: 'Member NPS', type: 'nps', status: 'live', closes_at: null, last_answer_at: null,
    channels: ['link'], segment: 'all', segments: [], responses: 12, views: 40, response_rate: 30, completed_all: null,
    main: { question_id: 'q', kind: 'nps', score: -33, change: null, counts: { '3': 5, '8': 3, '10': 4 } },
    questions: [], reasons: [], trend: [], by_segment: [],
    ...overrides,
  };
}

const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => {
  fetchMock.mockReset().mockResolvedValue(new Response(null, { status: 404 }));
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const renderTab = (o: SurveyOverview) =>
  render(
    <MemoryRouter>
      <OverviewTab overview={o} onReadAll={() => {}} />
    </MemoryRouter>,
  );

describe('OverviewTab extras', () => {
  it('shows close the loop only on standard surveys, linking to contact requests', () => {
    const { unmount } = renderTab(overview());
    expect(screen.getByRole('heading', { name: 'Close the loop' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /contact requests/i })).toHaveAttribute('href', '/contact-requests');
    unmount();
    renderTab(overview({ type: 'custom', main: null }));
    expect(screen.queryByRole('heading', { name: 'Close the loop' })).toBeNull();
  });

  it('AI banner text is exact, is not an alert and sends nothing', () => {
    renderTab(overview());
    expect(
      screen.getByText('AI summary of comments is coming soon. It will group comments into themes.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('shows trend and segments only when the data has them', () => {
    const { unmount } = renderTab(overview());
    expect(screen.queryByRole('heading', { name: /trend/i })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'By segment' })).toBeNull();
    unmount();
    renderTab(
      overview({
        trend: [{ month: '2026-10', score: 0, answers: 5 }, { month: '2026-11', score: 10, answers: 7 }],
        by_segment: [
          { value: 'a', label: 'Members', answers: 6, score: 10, counts: { '9': 3, '3': 3 } },
          { value: 'b', label: 'Guests', answers: 6, score: 0, counts: { '9': 2, '3': 2, '7': 2 } },
        ],
      }),
    );
    expect(screen.getByRole('heading', { name: /trend/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'By segment' })).toBeInTheDocument();
  });

  it('custom surveys get an In short sentence from the numbers', () => {
    renderTab(
      overview({
        type: 'custom', main: null,
        questions: [{ id: 'r', kind: 'rating', prompt: 'the information', required: false, answers: 10,
          options: [1, 2, 3, 4, 5].map((n) => ({ label: String(n), count: n === 5 ? 8 : n === 1 ? 2 : 0 })), average: 4 }],
      }),
    );
    expect(screen.getByRole('heading', { name: 'In short' })).toBeInTheDocument();
    expect(screen.getByText('“the information”: most respondents rated it 4–5 (80%).')).toBeInTheDocument();
  });
});
