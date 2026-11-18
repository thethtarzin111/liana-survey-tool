import type { SurveyOverview } from '../../api/client';
import { Card, CardBody, CardHeader } from '../../components/ui';
import { plural, signed } from './format';
import { groupsFor } from './groups';

type Kind = 'nps' | 'thumbs' | 'rating';
type Row = SurveyOverview['by_segment'][number];

const MIN_ANSWERS = 5;

/** One split bar and score per allowed group; hidden below two groups. Renders only what the API sends. */
export function SegmentCard({ kind, rows }: { kind: Kind; rows: Row[] }) {
  if (rows.length < 2) return null;
  const groups = groupsFor(kind);
  return (
    <Card>
      <CardHeader title="By segment" />
      <CardBody>
        <ul className="segment-rows">
          {rows.map((row) => {
            const parts = groups.map((g) => ({
              ...g,
              count: g.values.reduce((sum, v) => sum + (row.counts[v] ?? 0), 0),
            }));
            const total = parts.reduce((sum, p) => sum + p.count, 0);
            const hidden = row.answers < MIN_ANSWERS;
            return (
              <li key={row.value} className="segment-row">
                <span className="segment-label">{row.label}</span>
                {hidden ? (
                  <span className="segment-hidden">Fewer than 5 answers. Hidden to protect anonymity.</span>
                ) : (
                  <>
                    <span
                      className="segment-bar"
                      role="img"
                      aria-label={parts.map((p) => `${p.label} ${p.count}`).join(', ')}
                    >
                      {parts.map((p) =>
                        p.count > 0 ? (
                          <span
                            key={p.label}
                            className={`segment-part tone-${p.tone}`}
                            style={{ width: `${(p.count / total) * 100}%` }}
                            title={`${p.label}: ${p.count}`}
                          />
                        ) : null,
                      )}
                    </span>
                    <strong className="segment-score">
                      {row.score === null ? '—' : kind === 'nps' ? signed(row.score) : `${row.score}%`}
                    </strong>
                    <span className="segment-answers">{plural(row.answers, 'answer', 'answers')}</span>
                  </>
                )}
              </li>
            );
          })}
        </ul>
      </CardBody>
    </Card>
  );
}
