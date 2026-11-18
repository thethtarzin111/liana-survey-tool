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
});
