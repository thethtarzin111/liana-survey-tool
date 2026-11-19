import { render, screen } from '@testing-library/react';
import { SegmentCard } from './SegmentCard';

const row = (value: string, label: string, answers: number, score: number | null, counts: Record<string, number>) => ({
  value, label, answers, score, counts,
});
const rows = [
  row('members', 'Members', 8, 25, { '9': 4, '7': 2, '2': 2 }),
  row('guests', 'Guests', 6, -50, { '9': 1, '2': 4, '7': 1 }),
];

describe('SegmentCard', () => {
  it('is hidden with fewer than 2 groups', () => {
    const { container } = render(<SegmentCard kind="nps" rows={[rows[0]]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows each group with answers, score and a toned split bar', () => {
    const { container } = render(<SegmentCard kind="nps" rows={rows} />);
    expect(screen.getByRole('heading', { name: 'By segment' })).toBeInTheDocument();
    expect(screen.getByText('Members')).toBeInTheDocument();
    expect(screen.getByText('+25')).toBeInTheDocument();
    expect(screen.getByText('−50')).toBeInTheDocument();
    expect(screen.getByText('8 answers')).toBeInTheDocument();
    expect(container.querySelectorAll('.segment-part.tone-positive')).toHaveLength(2);
    expect(container.querySelectorAll('.segment-part.tone-negative')).toHaveLength(2);
  });

  it('never names a group that is not in the data', () => {
    const { container } = render(<SegmentCard kind="nps" rows={rows} />);
    const labels = [...container.querySelectorAll('.segment-label')].map((n) => n.textContent);
    expect(labels).toEqual(['Members', 'Guests']);
    expect(screen.queryByText(/Fewer than 5 answers/)).toBeNull();
  });

  it('never shows or names a row below 5 answers, even if the API sent one', () => {
    const { container } = render(
      <SegmentCard kind="nps" rows={[...rows, row('x', 'Alumni', 3, 33, { '9': 3 })]} />,
    );
    const labels = [...container.querySelectorAll('.segment-label')].map((n) => n.textContent);
    expect(labels).toEqual(['Members', 'Guests']);
    expect(screen.queryByText('Alumni')).toBeNull();
    expect(screen.queryByText('+33')).toBeNull();
  });

  it('counts groups after dropping small rows, so one group left hides the card', () => {
    const { container } = render(<SegmentCard kind="nps" rows={[rows[0], row('x', 'Alumni', 3, 33, { '9': 3 })]} />);
    expect(container.firstChild).toBeNull();
  });
});
