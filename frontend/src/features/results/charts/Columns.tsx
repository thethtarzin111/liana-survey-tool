import { plural } from '../format';
import { percentOf, toneClass, type Tone } from './tone';

export type ColumnBar = { label: string; count: number; tone: Tone };

type Props = { label: string; hideLabel?: boolean; bars: ColumnBar[]; note?: string };

/** Vertical bars, one per answer value, scaled to the tallest. */
export function Columns({ label, hideLabel, bars, note }: Props) {
  const total = bars.reduce((sum, b) => sum + b.count, 0);
  const max = Math.max(1, ...bars.map((b) => b.count));
  const summary = bars.map((b) => `${b.label} ${percentOf(b.count, total)}%`).join(', ');
  return (
    <figure className="chart columns">
      <figcaption className={hideLabel ? 'chart-label chart-label-hidden' : 'chart-label'}>{label}</figcaption>
      <div className="columns-plot" role="img" aria-label={summary}>
        {bars.map((b) => (
          <div
            key={b.label}
            className="columns-item"
            title={`${b.label}: ${plural(b.count, 'answer', 'answers')}, ${percentOf(b.count, total)}%`}
          >
            <span className="columns-count" aria-hidden="true">{b.count}</span>
            <div className="columns-track">
              <span
                className={`columns-bar ${toneClass(b.tone)}`}
                style={{ height: `${(b.count / max) * 100}%` }}
              />
            </div>
            <span className="columns-label" aria-hidden="true">{b.label}</span>
          </div>
        ))}
      </div>
      {note ? <figcaption className="chart-note">{note}</figcaption> : null}
    </figure>
  );
}
