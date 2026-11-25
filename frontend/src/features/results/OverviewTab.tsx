import type { SurveyOverview } from '../../api/client';
import { Card, EmptyState, icons } from '../../components/ui';
import { AnswerSplit, TopReasons, hasTopReasons } from './AnswerSplit';
import { CloseTheLoop } from './CloseTheLoop';
import { InsightsCard } from './InsightsCard';
import { KpiCards } from './KpiCards';
import { QuestionCard } from './QuestionCard';
import { SegmentCard } from './SegmentCard';
import { takeaway } from './takeaway';
import { TrendCard } from './TrendCard';

type Props = {
  overview: SurveyOverview;
  onReadAll: () => void;
  /** Opens the Comment insights tab; left out when the survey asks for no comments. */
  onOpenInsights?: () => void;
};

/** KPI cards, then the visual of each question kind. */
export function OverviewTab({ overview, onReadAll, onOpenInsights }: Props) {
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
  const custom = overview.type === 'custom';
  const trendCard = kind && overview.trend.length >= 2 ? <TrendCard kind={kind} trend={overview.trend} /> : null;
  const reasonsCard = !custom && hasTopReasons(overview) ? <TopReasons overview={overview} /> : null;
  const pair = [reasonsCard, trendCard].filter(Boolean);
  return (
    <div className="results-overview">
      <KpiCards overview={overview} />
      {custom ? (
        <>
          {overview.questions.length > 0 ? (
            <div className="results-row">
              {overview.questions.map((q) => (
                <QuestionCard key={q.id} question={q} onReadAll={onReadAll} />
              ))}
            </div>
          ) : null}
          {short ? (
            <Card className="results-card">
              <h2 className="results-card-title">In short</h2>
              <p className="results-short-text">{short}</p>
            </Card>
          ) : null}
        </>
      ) : (
        <AnswerSplit overview={overview} />
      )}
      {pair.length > 0 ? <div className="results-row">{pair}</div> : null}
      {onOpenInsights ? <InsightsCard onOpen={onOpenInsights} /> : null}
      {kind ? <SegmentCard kind={kind} rows={overview.by_segment} /> : null}
      <CloseTheLoop type={overview.type} />
    </div>
  );
}
