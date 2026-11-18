import { fireEvent, render, screen } from '@testing-library/react';
import type { OverviewQuestion, SurveyOverview } from '../../api/client';
import { AnswerSplit } from './AnswerSplit';
import { QuestionCard } from './QuestionCard';

function question(overrides: Partial<OverviewQuestion>): OverviewQuestion {
  return { id: 'q', kind: 'single_choice', prompt: 'Question', required: false, answers: 4, options: [], average: null, ...overrides };
}
const opts = (n: number) => Array.from({ length: n }, (_, i) => ({ label: `Option ${i + 1}`, count: 1 }));

describe('QuestionCard', () => {
  it('multiple choice shows the more-than-100% note', () => {
    render(<QuestionCard onReadAll={() => {}} question={question({ kind: 'multiple_choice', options: opts(3) })} />);
    expect(screen.getByText(/add up to more than 100%/)).toBeInTheDocument();
  });

  it('dropdown with 7 options uses bars, with 6 a donut', () => {
    const { container, rerender } = render(
      <QuestionCard onReadAll={() => {}} question={question({ kind: 'dropdown', answers: 7, options: opts(7) })} />,
    );
    expect(container.querySelector('.barlist')).not.toBeNull();
    expect(container.querySelector('.donut')).toBeNull();
    rerender(<QuestionCard onReadAll={() => {}} question={question({ kind: 'dropdown', answers: 6, options: opts(6) })} />);
    expect(container.querySelector('.donut')).not.toBeNull();
  });

  it('text question shows count and "Read all answers →" which switches to Responses', () => {
    const onReadAll = vi.fn();
    render(<QuestionCard onReadAll={onReadAll} question={question({ kind: 'text', answers: 3 })} />);
    expect(screen.getAllByText('3 answers').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Read all answers →' }));
    expect(onReadAll).toHaveBeenCalledTimes(1);
  });

  it('plurals: "1 answer"', () => {
    render(<QuestionCard onReadAll={() => {}} question={question({ kind: 'long_text', answers: 1 })} />);
    expect(screen.getAllByText('1 answer').length).toBeGreaterThan(0);
    expect(screen.queryByText('1 answers')).toBeNull();
  });

  it('nps columns 0–10 coloured by group', () => {
    const options = Array.from({ length: 11 }, (_, i) => ({ label: String(i), count: 1 }));
    const { container } = render(<QuestionCard onReadAll={() => {}} question={question({ kind: 'nps', answers: 11, options })} />);
    const bars = [...container.querySelectorAll('.columns-bar')];
    expect(bars).toHaveLength(11);
    expect(bars.slice(0, 7).every((b) => b.classList.contains('tone-negative'))).toBe(true);
    expect(bars.slice(7, 9).every((b) => b.classList.contains('tone-neutral'))).toBe(true);
    expect(bars.slice(9).every((b) => b.classList.contains('tone-positive'))).toBe(true);
  });
});

describe('AnswerSplit', () => {
  it('shows a negative NPS with its sign and never as a positive slice', () => {
    const overview = {
      type: 'nps', responses: 12, reasons: [{ label: 'Price', count: 3, percent: 25 }],
      main: { question_id: 'q', kind: 'nps', score: -33, change: null, counts: { '3': 8, '10': 4 } },
    } as unknown as SurveyOverview;
    const { container } = render(<AnswerSplit overview={overview} />);
    expect(screen.getByText('−33')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Detractors 67%, Passives 0%, Promoters 33%' })).toBeInTheDocument();
    expect(container.querySelector('.donut-slice.tone-negative')).not.toBeNull();
    expect(screen.getByText('Top reasons', { selector: 'h3' })).toBeInTheDocument();
  });
});
