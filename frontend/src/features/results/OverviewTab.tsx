import type { SurveyOverview } from '../../api/client';
import { EmptyState, icons } from '../../components/ui';
import { AnswerSplit } from './AnswerSplit';
import { KpiCards } from './KpiCards';
import { QuestionCard } from './QuestionCard';

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
  return (
    <div className="results-overview">
      <KpiCards overview={overview} />
      {overview.type === 'custom' ? (
        overview.questions.map((q) => <QuestionCard key={q.id} question={q} onReadAll={onReadAll} />)
      ) : (
        <AnswerSplit overview={overview} />
      )}
    </div>
  );
}
