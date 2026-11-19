import type { OverviewQuestion } from '../../api/client';
import { Button, Card } from '../../components/ui';
import { BarList } from './charts/BarList';
import { Columns } from './charts/Columns';
import { Donut } from './charts/Donut';
import { percentOf } from './charts/tone';
import { plural, signed } from './format';
import { groupSlices, THUMBS_LABEL, toneOf } from './groups';

const MORE_THAN_ONE = 'People could pick more than one, so the percentages add up to more than 100%.';
const MAX_DONUT_OPTIONS = 6;

function visual(q: OverviewQuestion, onReadAll: () => void) {
  const isText = q.kind === 'text' || q.kind === 'long_text';
  if (q.answers === 0 && !isText) return <p className="question-empty">No answers yet</p>;
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
          hideLabel
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
            hideLabel
            rows={q.options.map((o) => ({ label: o.label, count: o.count, percent: percentOf(o.count, optionTotal) }))}
          />
        );
      }
      return (
        <Donut
          label={q.prompt}
          hideLabel
          center={String(q.answers)}
          centerNote={q.answers === 1 ? 'answer' : 'answers'}
          slices={q.options.map((o, i) => ({ label: o.label, count: o.count, tone: i }))}
        />
      );
    case 'reasons':
      return (
        <BarList
          label={q.prompt}
          hideLabel
          rows={q.options
            .slice()
            .sort((a, b) => b.count - a.count)
            .map((o) => ({ label: o.label, count: o.count, percent: percentOf(o.count, q.answers) }))}
        />
      );
    case 'nps':
    case 'rating':
    case 'thumbs': {
      const kind = q.kind;
      const counts = Object.fromEntries(q.options.map((o) => [o.label, o.count]));
      const slices = groupSlices(kind, counts);
      const count = (label: string) => slices.find((s) => s.label === label)?.count ?? 0;
      const share = (label: string) => percentOf(count(label), optionTotal);
      const bars = q.options.map((o, i) => ({
        label: kind === 'thumbs' ? (THUMBS_LABEL[o.label] ?? o.label) : o.label,
        count: o.count,
        tone: toneOf(kind, kind === 'thumbs' ? String(i) : o.label),
      }));
      return (
        <>
          {kind !== 'rating' ? (
            <Donut
              label={q.prompt}
              hideLabel
              center={String(optionTotal)}
              centerNote={optionTotal === 1 ? 'answer' : 'answers'}
              slices={slices}
            />
          ) : null}
          <Columns label={q.prompt} hideLabel bars={bars} />
          <p className="question-numbers">
            {kind === 'nps' ? (
              <>
                <strong>NPS {signed(percentOf(count('Promoters') - count('Detractors'), optionTotal))}</strong>
                <span>Promoters {share('Promoters')}%</span>
                <span>Detractors {share('Detractors')}%</span>
              </>
            ) : kind === 'thumbs' ? (
              <>
                <strong>Positive {share('Good') + share('Loved it')}%</strong>
                <span>Loved it {share('Loved it')}%</span>
              </>
            ) : (
              <>
                <strong>Satisfied (4–5) {share('Satisfied')}%</strong>
                <span>Average {q.average == null ? '—' : q.average.toFixed(1)}</span>
              </>
            )}
          </p>
        </>
      );
    }
  }
}

/** One question of a custom survey, drawn the way its kind is best read. */
export function QuestionCard({ question, onReadAll }: { question: OverviewQuestion; onReadAll: () => void }) {
  return (
    <Card as="article" className="results-card">
      <div className="results-card-head">
        <h3 className="results-card-title">{question.prompt}</h3>
        <span className="results-count">{plural(question.answers, 'answer', 'answers')}</span>
      </div>
      {visual(question, onReadAll)}
    </Card>
  );
}
