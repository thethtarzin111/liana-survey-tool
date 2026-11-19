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

describe('OverviewTab order', () => {
  const trend = [{ month: '2026-10', score: 0, answers: 5 }, { month: '2026-11', score: 10, answers: 7 }];
  const by_segment: SurveyOverview['by_segment'] = [
    { value: 'a', label: 'Members', answers: 6, score: 10, counts: { '9': 3, '3': 3 } },
    { value: 'b', label: 'Guests', answers: 6, score: 0, counts: { '9': 2, '3': 2, '7': 2 } },
  ];
  /** The elements in document order must follow the given list. */
  function expectOrder(elements: (Element | null)[]) {
    elements.forEach((el, i) => {
      expect(el, `element ${i} is missing`).not.toBeNull();
      if (i === 0) return;
      const before = elements[i - 1] as Element;
      expect(before.compareDocumentPosition(el as Element) & Node.DOCUMENT_POSITION_FOLLOWING, `element ${i} comes after ${i - 1}`).toBeTruthy();
    });
  }
  const heading = (name: string | RegExp) => screen.getByRole('heading', { name });

  it('standard survey: KPIs, split and distribution, AI and reasons, trend, segments, close the loop', () => {
    const { container } = renderTab(overview({ reasons: [{ label: 'Price', count: 3, percent: 25 }], trend, by_segment }));
    expectOrder([
      container.querySelector('.results-kpis'),
      screen.getByText('Answer split'),
      screen.getByText('Distribution'),
      heading('AI summary of comments'),
      heading('Top reasons'),
      heading(/trend/i),
      heading('By segment'),
      heading('Close the loop'),
    ]);
    const rows = container.querySelectorAll('.results-row');
    expect(rows[0].textContent).toContain('Answer split');
    expect(rows[0].textContent).toContain('Distribution');
    expect(rows[1]).toHaveClass('results-row-ai');
    expect(rows[1].textContent).toContain('AI summary of comments');
    expect(rows[1].textContent).toContain('Top reasons');
  });

  it('standard survey without reasons: the AI card spans its row', () => {
    const { container } = renderTab(overview());
    const row = container.querySelector('.results-row-ai') as HTMLElement;
    expect(row).toHaveClass('results-row-solo');
    expect(screen.queryByRole('heading', { name: 'Top reasons' })).toBeNull();
  });

  it('custom survey: KPIs, questions, AI and In short, trend, segments', () => {
    const { container } = renderTab(
      overview({
        type: 'custom', main: null, trend: [], by_segment: [],
        questions: [{ id: 'r', kind: 'rating', prompt: 'the information', required: false, answers: 10,
          options: [1, 2, 3, 4, 5].map((n) => ({ label: String(n), count: n === 5 ? 8 : n === 1 ? 2 : 0 })), average: 4 }],
      }),
    );
    expectOrder([
      container.querySelector('.results-kpis'),
      screen.getByRole('heading', { name: 'the information' }),
      heading('AI summary of comments'),
      heading('In short'),
    ]);
    expect(screen.queryByRole('heading', { name: 'Close the loop' })).toBeNull();
  });

  it('custom survey without a takeaway: the AI card spans its row', () => {
    const { container } = renderTab(overview({ type: 'custom', main: null, questions: [] }));
    expect(container.querySelector('.results-row-ai')).toHaveClass('results-row-solo');
    expect(screen.queryByRole('heading', { name: 'In short' })).toBeNull();
  });
});
