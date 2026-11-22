import { render, screen } from '@testing-library/react';
import { TrendCard } from './TrendCard';

const nps = { kind: 'nps' as const };

describe('TrendCard', () => {
  it('is hidden with one month', () => {
    const { container } = render(<TrendCard kind="nps" trend={[{ month: '2026-11', score: 40, answers: 9 }]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('draws a line with month and value labels from two months', () => {
    const trend = [
      { month: '2026-09', score: -10, answers: 5 },
      { month: '2026-10', score: 20, answers: 8 },
      { month: '2026-11', score: 40, answers: 9 },
    ];
    const { container } = render(<TrendCard kind={nps.kind} trend={trend} />);
    expect(container.querySelector('polyline')).not.toBeNull();
    for (const text of ['Sep', 'Oct', 'Nov', '−10', '+20', '+40']) {
      expect(screen.getAllByText(text).length).toBeGreaterThan(0);
    }
    const chart = screen.getByRole('img');
    expect(chart).toHaveAttribute('aria-label', expect.stringContaining('Sep −10'));
    expect(chart).toHaveAttribute('aria-label', expect.stringContaining('Oct +20'));
    expect(chart).toHaveAttribute('aria-label', expect.stringContaining('Nov +40'));
  });

  it('shows percent for other scores', () => {
    render(
      <TrendCard
        kind="thumbs"
        trend={[{ month: '2026-10', score: 50, answers: 4 }, { month: '2026-11', score: 60, answers: 5 }]}
      />,
    );
    expect(screen.getAllByText('60%').length).toBeGreaterThan(0);
  });
});
