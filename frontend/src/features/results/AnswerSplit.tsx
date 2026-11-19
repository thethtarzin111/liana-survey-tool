import type { SurveyOverview } from '../../api/client';
import { Card } from '../../components/ui';
import { AiRow } from './AiComingSoon';
import { BarList } from './charts/BarList';
import { Columns } from './charts/Columns';
import { Donut } from './charts/Donut';
import { percentOf } from './charts/tone';
import { signed } from './format';
import { groupSlices, scaleValues, THUMBS_LABEL, toneOf } from './groups';

/** Standard surveys: the main question as a donut and a distribution chart, then the top reasons. */
export function AnswerSplit({ overview }: { overview: SurveyOverview }) {
  const { main, reasons } = overview;
  if (!main) return null;
  const counts = main.counts;
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  const slices = groupSlices(main.kind, counts);
  const center =
    main.score === null ? '—' : main.kind === 'nps' ? signed(main.score) : `${main.score}%`;
  const centerNote = main.kind === 'nps' ? 'NPS' : main.kind === 'thumbs' ? 'positive' : 'satisfied';
  const bars = scaleValues(main.kind).map((v) => ({
    label: main.kind === 'thumbs' ? THUMBS_LABEL[v] : v,
    count: counts[v] ?? 0,
    tone: toneOf(main.kind, v),
  }));
  const topReasons = reasons.map((r) => ({
    label: r.label,
    count: r.count,
    percent: r.percent ?? percentOf(r.count, overview.responses),
  }));
  const showReasons = total > 0 && topReasons.length > 0;
  return (
    <>
      <div className="results-row">
        <Card className="results-card">
          <Donut label="Answer split" center={center} centerNote={centerNote} slices={slices} />
        </Card>
        <Card className="results-card">
          <Columns label="Distribution" bars={bars} />
        </Card>
      </div>
      <AiRow>
        {showReasons ? (
          <Card className="results-card">
            <h3 className="results-card-title">Top reasons</h3>
            <BarList label="Top reasons" hideLabel rows={topReasons} />
          </Card>
        ) : null}
      </AiRow>
    </>
  );
}
