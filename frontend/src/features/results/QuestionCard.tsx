import type { OverviewQuestion } from '../../api/client';
import { Button, Card, CardBody, CardHeader } from '../../components/ui';
import { BarList } from './charts/BarList';
import { Columns } from './charts/Columns';
import { Donut } from './charts/Donut';
import { percentOf } from './charts/tone';
import { plural } from './format';
import { RATING_GROUPS, THUMBS_LABEL, toneOf } from './groups';

const MORE_THAN_ONE = 'People could pick more than one, so the percentages add up to more than 100%.';
const MAX_DONUT_OPTIONS = 6;

function visual(q: OverviewQuestion, onReadAll: () => void) {
  const optionTotal = q.options.reduce((sum, o) => sum + o.count, 0);
  switch (q.kind) {
    case 'text':
    case 'long_text':
      return (
        <div className="question-text">
          <strong>{plural(q.answers, 'answer', 'answers')}</strong>
          <Button variant="ghost" onClick={onReadAll}>Read all answers →</Button>
        </div>
      );
    case 'multiple_choice':
      return (
        <BarList
          label={q.prompt}
          note={MORE_THAN_ONE}
          rows={q.options.map((o) => ({ label: o.label, count: o.count, percent: percentOf(o.count, q.answers) }))}
        />
      );
    case 'single_choice':
    case 'dropdown':
      if (q.options.length > MAX_DONUT_OPTIONS) {
        return (
          <BarList
            label={q.prompt}
            rows={q.options.map((o) => ({ label: o.label, count: o.count, percent: percentOf(o.count, optionTotal) }))}
          />
        );
      }
      return (
        <Donut
          label={q.prompt}
          center={String(q.answers)}
          centerNote={q.answers === 1 ? 'answer' : 'answers'}
          slices={q.options.map((o, i) => ({ label: o.label, count: o.count, tone: i }))}
        />
      );
    case 'reasons':
      return (
        <BarList
          label={q.prompt}
          rows={q.options
            .slice()
            .sort((a, b) => b.count - a.count)
            .map((o) => ({ label: o.label, count: o.count, percent: percentOf(o.count, q.answers) }))}
        />
      );
    case 'nps':
    case 'rating':
    case 'thumbs': {
      const bars = q.options.map((o, i) => ({
        label: q.kind === 'thumbs' ? (THUMBS_LABEL[o.label] ?? o.label) : o.label,
        count: o.count,
        tone: toneOf(q.kind as 'nps' | 'rating' | 'thumbs', q.kind === 'thumbs' ? String(i) : o.label),
      }));
      const satisfied = q.options.filter((o) => RATING_GROUPS[2].values.includes(o.label)).reduce((n, o) => n + o.count, 0);
      return (
        <>
          <Columns label={q.prompt} bars={bars} />
          {q.kind === 'rating' ? (
            <p className="question-numbers">
              <strong>Satisfied (4–5) {percentOf(satisfied, optionTotal)}%</strong>
              <span>Average {q.average == null ? '—' : q.average.toFixed(1)}</span>
            </p>
          ) : null}
        </>
      );
    }
  }
}

/** One question of a custom survey, drawn the way its kind is best read. */
export function QuestionCard({ question, onReadAll }: { question: OverviewQuestion; onReadAll: () => void }) {
  return (
    <Card as="article">
      <CardHeader
        title={question.prompt}
        level={3}
        actions={<span className="results-count">{plural(question.answers, 'answer', 'answers')}</span>}
      />
      <CardBody>{visual(question, onReadAll)}</CardBody>
    </Card>
  );
}
