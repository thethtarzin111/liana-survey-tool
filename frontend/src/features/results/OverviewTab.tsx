import type { SurveyOverview } from '../../api/client';
import { Card, EmptyState, icons } from '../../components/ui';
import { AiComingSoon } from './AiComingSoon';
import { AnswerSplit } from './AnswerSplit';
import { CloseTheLoop } from './CloseTheLoop';
import { KpiCards } from './KpiCards';
import { QuestionCard } from './QuestionCard';
import { SegmentCard } from './SegmentCard';
import { takeaway } from './takeaway';
import { TrendCard } from './TrendCard';

/** KPI cards, then the visual of each question kind. */
export function OverviewTab({ overview, onReadAll }: { overview: SurveyOverview; onReadAll: () => void }) {
  if (overview.responses === 0) {
    return (
      <EmptyState
        icon={icons.chart}
        title="No answers yet"
        text={
          overview.segment === 'all'
            ? 'Results show up here as soon as people answer this survey.'
            : 'Nobody in this segment has answered yet.'
        }
      />
    );
  }
  const short = overview.type === 'custom' ? takeaway(overview) : null;
  const kind = overview.main?.kind;
  return (
    <div className="results-overview">
      <KpiCards overview={overview} />
      {short ? (
        <Card padded>
          <h2 className="results-short-title">In short</h2>
          <p className="results-short-text">{short}</p>
        </Card>
      ) : null}
      {kind ? <TrendCard kind={kind} trend={overview.trend} /> : null}
      {overview.type === 'custom' ? (
        overview.questions.map((q) => <QuestionCard key={q.id} question={q} onReadAll={onReadAll} />)
      ) : (
        <AnswerSplit overview={overview} />
      )}
      {kind ? <SegmentCard kind={kind} rows={overview.by_segment} /> : null}
      <AiComingSoon />
      <CloseTheLoop type={overview.type} />
    </div>
  );
}
