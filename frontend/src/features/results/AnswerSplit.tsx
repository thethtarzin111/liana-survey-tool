import type { SurveyOverview } from '../../api/client';
import { Card } from '../../components/ui';
import { BarList } from './charts/BarList';
import { Columns } from './charts/Columns';
import { Donut } from './charts/Donut';
import { percentOf } from './charts/tone';
import { signed } from './format';
import { groupSlices, scaleValues, THUMBS_LABEL, toneOf } from './groups';

/** Standard surveys: the main question as a donut next to its distribution chart. */
export function AnswerSplit({ overview }: { overview: SurveyOverview }) {
  const { main } = overview;
  if (!main) return null;
  const counts = main.counts;
  const slices = groupSlices(main.kind, counts);
  const center =
    main.score === null ? '—' : main.kind === 'nps' ? signed(main.score) : `${main.score}%`;
  const centerNote = main.kind === 'nps' ? 'NPS' : main.kind === 'thumbs' ? 'positive' : 'satisfied';
  const bars = scaleValues(main.kind).map((v) => ({
    label: main.kind === 'thumbs' ? THUMBS_LABEL[v] : v,
    count: counts[v] ?? 0,
    tone: toneOf(main.kind, v),
  }));
  return (
    <div className="results-row">
      <Card className="results-card">
        <Donut label="Answer split" center={center} centerNote={centerNote} slices={slices} />
      </Card>
      <Card className="results-card">
        <Columns label="Distribution" bars={bars} />
      </Card>
    </div>
  );
}

/** Whether a standard survey has top reasons to show. */
export function hasTopReasons(overview: SurveyOverview): boolean {
  return Boolean(overview.main) && overview.responses > 0 && overview.reasons.length > 0;
}

/** Top reasons of a standard survey, or null when there are none. */
export function TopReasons({ overview }: { overview: SurveyOverview }) {
  const total = overview.responses;
  const rows = overview.reasons.map((r) => ({
    label: r.label,
    count: r.count,
    percent: r.percent ?? percentOf(r.count, total),
  }));
  if (!hasTopReasons(overview)) return null;
  return (
    <Card className="results-card">
      <h3 className="results-card-title">Top reasons</h3>
      <BarList label="Top reasons" hideLabel rows={rows} />
    </Card>
  );
}
