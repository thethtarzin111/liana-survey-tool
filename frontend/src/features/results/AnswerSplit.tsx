import type { SurveyOverview } from '../../api/client';
import { Card, CardBody, CardHeader } from '../../components/ui';
import { BarList } from './charts/BarList';
import { Columns } from './charts/Columns';
import { Donut } from './charts/Donut';
import { percentOf } from './charts/tone';
import { signed } from './format';
import { groupsFor, scaleValues, THUMBS_LABEL, toneOf } from './groups';

/** Standard surveys: the main question as a donut and a distribution chart, then the top reasons. */
export function AnswerSplit({ overview }: { overview: SurveyOverview }) {
  const { main, reasons } = overview;
  if (!main) return null;
  const counts = main.counts;
  const groups = groupsFor(main.kind);
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  const slices = groups.map((g) => ({
    label: g.label,
    tone: g.tone,
    count: g.values.reduce((sum, v) => sum + (counts[v] ?? 0), 0),
  }));
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
  return (
    <>
      <div className="results-split">
        <Card padded>
          <Donut label="Answer split" center={center} centerNote={centerNote} slices={slices} />
        </Card>
        <Card padded>
          <Columns label="Distribution" bars={bars} />
        </Card>
      </div>
      {total > 0 && topReasons.length > 0 ? (
        <Card>
          <CardHeader title="Top reasons" level={3} />
          <CardBody>
            <BarList label="Top reasons" rows={topReasons} />
          </CardBody>
        </Card>
      ) : null}
    </>
  );
}
