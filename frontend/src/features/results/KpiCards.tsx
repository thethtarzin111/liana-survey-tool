import type { SurveyOverview } from '../../api/client';
import { Card } from '../../components/ui';
import { plural, signed } from './format';

type Kpi = { label: string; value: string; note?: string; tone?: 'up' | 'down'; arrow?: string };

const sum = (counts: Record<string, number>, keys?: string[]) =>
  Object.entries(counts).reduce((total, [key, n]) => (!keys || keys.includes(key) ? total + n : total), 0);
const percent = (part: number, whole: number) => (whole ? Math.round((part / whole) * 100) : 0);
const range = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => String(from + i));

/** "October" when it is November. */
function previousMonthName(now = new Date()): string {
  return new Date(now.getFullYear(), now.getMonth() - 1, 1).toLocaleDateString('en-GB', { month: 'long' });
}

function scoreCard(overview: SurveyOverview): Kpi | null {
  const { main, type } = overview;
  if (!main) return null;
  const label = type === 'nps' ? 'NPS' : type === 'thumbs' ? 'Positive (Good + Loved it)' : 'Satisfied (4–5)';
  const value = main.score === null ? '—' : type === 'nps' ? signed(main.score) : `${main.score}%`;
  const kpi: Kpi = { label, value };
  if (main.change !== null) {
    kpi.note = `${signed(main.change)} since ${previousMonthName()}`;
    kpi.arrow = main.change > 0 ? '↑' : main.change < 0 ? '↓' : '→';
    kpi.tone = main.change > 0 ? 'up' : main.change < 0 ? 'down' : undefined;
  } else if (type === 'nps') {
    kpi.note = 'scale −100 to +100';
  }
  return kpi;
}

function kpisFor(overview: SurveyOverview): Kpi[] {
  const { type, main, responses, views, response_rate, segment, segments } = overview;
  const segmentLabel = segments.find((s) => s.value === segment)?.label ?? segment;
  const rate: Kpi =
    segment !== 'all'
      ? { label: 'Response rate', value: '—', note: 'Not available per segment' }
      : response_rate === null
        ? { label: 'Response rate', value: '—', note: 'No views yet' }
        : { label: 'Response rate', value: `${response_rate}%`, note: `${responses} of ${views} viewed` };
  const count: Kpi = {
    label: 'Responses',
    value: responses.toLocaleString('en-US'),
    note: segment === 'all' ? 'all segments' : `segment: ${segmentLabel}`,
  };
  const score = scoreCard(overview);
  const counts = main?.counts ?? {};
  const total = sum(counts);

  if (type === 'thumbs') {
    const loved = counts['2'] ?? 0;
    return [score, count, rate, { label: 'Loved it', value: `${percent(loved, total)}%`, note: plural(loved, 'answer', 'answers') }].filter(
      (k): k is Kpi => k !== null,
    );
  }
  if (type === 'nps') {
    const promoters = sum(counts, ['9', '10']);
    const detractors = sum(counts, range(0, 6));
    return [
      score,
      count,
      rate,
      { label: 'Promoters', value: `${percent(promoters, total)}%`, note: `vs ${percent(detractors, total)}% detractors` },
    ].filter((k): k is Kpi => k !== null);
  }
  if (type === 'csat') {
    const average = overview.questions.find((q) => q.id === main?.question_id)?.average;
    return [
      score,
      count,
      rate,
      { label: 'Average rating', value: average == null ? '—' : average.toFixed(1), note: 'out of 5' },
    ].filter((k): k is Kpi => k !== null);
  }
  const cards: Kpi[] = [
    count,
    rate,
    {
      label: 'Completed all questions',
      value: overview.completed_all === null ? '—' : `${overview.completed_all}%`,
      note: 'the rest skipped optional ones',
    },
  ];
  const rating = overview.questions.find((q) => q.kind === 'rating' && q.average !== null);
  if (rating?.average != null) {
    cards.push({ label: 'Average rating', value: rating.average.toFixed(1), note: rating.prompt });
  }
  return cards;
}

/** The numbers at the top of the Overview tab, per survey type. */
export function KpiCards({ overview }: { overview: SurveyOverview }) {
  return (
    <ul className="results-kpis">
      {kpisFor(overview).map((kpi) => (
        <li key={kpi.label}>
          <Card as="div" className="results-kpi">
            <span className="results-kpi-label">{kpi.label}</span>
            <strong className="results-kpi-value">{kpi.value}</strong>
            {kpi.note ? (
              <span className={['results-kpi-note', kpi.tone].filter(Boolean).join(' ')}>
                {kpi.arrow ? <span aria-hidden="true">{kpi.arrow} </span> : null}
                {kpi.note}
              </span>
            ) : null}
          </Card>
        </li>
      ))}
    </ul>
  );
}
