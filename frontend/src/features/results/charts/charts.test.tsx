import { render, screen } from '@testing-library/react';
import { BarList } from './BarList';
import { Columns } from './Columns';
import { Donut } from './Donut';

describe('charts', () => {
  it('each chart has a text alternative listing every value', () => {
    render(
      <>
        <Donut
          label="Answer split"
          center="−33"
          centerNote="NPS"
          slices={[
            { label: 'Detractors', count: 8, tone: 'negative' },
            { label: 'Passives', count: 0, tone: 'neutral' },
            { label: 'Promoters', count: 4, tone: 'positive' },
          ]}
        />
        <Columns label="Distribution" bars={[{ label: 'Yes', count: 3, tone: 0 }, { label: 'No', count: 1, tone: 1 }]} />
        <BarList label="Reasons" rows={[{ label: 'Price', count: 2, percent: 50 }, { label: 'Speed', count: 1, percent: 25 }]} />
      </>,
    );
    expect(screen.getByRole('img', { name: 'Detractors 67%, Passives 0%, Promoters 33%' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Yes 75%, No 25%' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Price 50%, Speed 25%' })).toBeInTheDocument();
  });

  it('negative NPS keeps its sign and negative colour', () => {
    const { container } = render(
      <Donut
        label="Answer split"
        center="−33"
        centerNote="NPS"
        slices={[
          { label: 'Detractors', count: 8, tone: 'negative' },
          { label: 'Promoters', count: 4, tone: 'positive' },
        ]}
      />,
    );
    expect(screen.getByText('−33')).toBeInTheDocument();
    expect(container.querySelector('circle.tone-negative')).not.toBeNull();
    expect(container.querySelectorAll('circle.tone-positive')).toHaveLength(1);
  });

  it('gives each bar a tooltip with its count and percent', () => {
    render(<Columns label="Distribution" bars={[{ label: '9', count: 1, tone: 'positive' }, { label: '3', count: 3, tone: 'negative' }]} />);
    expect(screen.getByTitle('9: 1 answer, 25%')).toBeInTheDocument();
    expect(screen.getByTitle('3: 3 answers, 75%')).toBeInTheDocument();
  });

  it('draws slices with dasharray and dashoffset from their share', () => {
    const { container } = render(
      <Donut label="L" center="c" centerNote="n" slices={[{ label: 'A', count: 3, tone: 'positive' }, { label: 'B', count: 1, tone: 'neutral' }]} />,
    );
    const [a, b] = [...container.querySelectorAll('circle.donut-slice')];
    expect(a.getAttribute('stroke-dasharray')).toBe('75 25');
    expect(a.getAttribute('stroke-dashoffset')).toBe('25');
    expect(b.getAttribute('stroke-dasharray')).toBe('25 75');
    expect(b.getAttribute('stroke-dashoffset')).toBe('-50');
  });

  it('a single slice fills the whole ring', () => {
    const { container } = render(
      <Donut label="L" center="c" centerNote="n" slices={[{ label: 'A', count: 5, tone: 'positive' }, { label: 'B', count: 0, tone: 'neutral' }]} />,
    );
    const slices = container.querySelectorAll('circle.donut-slice');
    expect(slices).toHaveLength(1);
    expect(slices[0].getAttribute('stroke-dasharray')).toBe('100 0');
    expect(screen.getByRole('img', { name: 'A 100%, B 0%' })).toBeInTheDocument();
  });

  it('zero total draws only the track and 0% labels', () => {
    const { container } = render(
      <Donut label="L" center="—" centerNote="n" slices={[{ label: 'A', count: 0, tone: 'positive' }, { label: 'B', count: 0, tone: 'neutral' }]} />,
    );
    expect(container.querySelectorAll('circle.donut-slice')).toHaveLength(0);
    expect(container.querySelector('circle.donut-track')).not.toBeNull();
    expect(screen.getByRole('img', { name: 'A 0%, B 0%' })).toBeInTheDocument();
  });

  it('the negative slice is stroked with the striped pattern', () => {
    const { container } = render(
      <Donut label="L" center="c" centerNote="n" slices={[{ label: 'A', count: 1, tone: 'negative' }, { label: 'B', count: 1, tone: 'positive' }]} />,
    );
    const id = container.querySelector('pattern')?.id;
    expect(id).toBeTruthy();
    expect(container.querySelector('circle.tone-negative')?.getAttribute('stroke')).toBe(`url(#${id})`);
    expect(container.querySelector('circle.tone-positive')?.getAttribute('stroke')).toBeNull();
  });

  it('the negative slice falls back to the token colour when the pattern cannot be used', () => {
    const { container } = render(
      <Donut label="L" center="c" centerNote="n" slices={[{ label: 'A', count: 1, tone: 'negative' }, { label: 'B', count: 1, tone: 'positive' }]} />,
    );
    const id = container.querySelector('pattern')?.id;
    const circle = container.querySelector('circle.tone-negative') as SVGElement;
    expect(circle.getAttribute('style')).toContain(`url(#${id}) var(--color-chart-negative)`);
  });

  it('donut keeps a fixed-size ring and a viewBox that holds the whole stroke', () => {
    const { container } = render(
      <Donut label="L" center="c" centerNote="n" slices={[{ label: 'A', count: 3, tone: 'positive' }, { label: 'B', count: 1, tone: 'neutral' }]} />,
    );
    expect(container.querySelector('.donut-ring')).not.toBeNull();
    const svg = container.querySelector('.donut-ring svg') as SVGSVGElement;
    const [x, y, w, h] = (svg.getAttribute('viewBox') ?? '').split(/\s+/).map(Number);
    expect([x, y]).toEqual([0, 0]);
    expect(w).toBe(h);
    for (const c of container.querySelectorAll('circle')) {
      const r = Number(c.getAttribute('r'));
      const stroke = Number(c.getAttribute('stroke-width'));
      expect(Number(c.getAttribute('cx')) - (r + stroke / 2)).toBeGreaterThanOrEqual(0);
      expect(Number(c.getAttribute('cx')) + (r + stroke / 2)).toBeLessThanOrEqual(w);
      expect(Number(c.getAttribute('cy')) + (r + stroke / 2)).toBeLessThanOrEqual(h);
    }
  });

  it('columns show the count above each bar and the label below', () => {
    const { container } = render(<Columns label="D" bars={[{ label: 'Yes', count: 3, tone: 0 }]} />);
    const item = container.querySelector('.columns-item') as HTMLElement;
    const kids = [...item.querySelectorAll('.columns-count, .columns-bar, .columns-label')].map((e) => e.className.split(' ')[0]);
    expect(kids).toEqual(['columns-count', 'columns-bar', 'columns-label']);
    expect(item.querySelector('.columns-count')?.textContent).toBe('3');
  });
});
