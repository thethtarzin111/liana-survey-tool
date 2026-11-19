import { useId } from 'react';
import { plural } from '../format';
import { percentOf, toneClass, type Tone } from './tone';

export type DonutSlice = { label: string; count: number; tone: Tone };

type Props = { label: string; hideLabel?: boolean; center: string; centerNote: string; slices: DonutSlice[] };

const RADIUS = 15.9155; // circumference 100, so a dash length is a percentage
const STROKE = 5;
const CENTER = 20;
// The view box holds the ring and half of its stroke on each side, so nothing is cut off.
const VIEW = CENTER * 2;

/** A ring split into slices, with the headline number in the middle and a legend beside it. */
export function Donut({ label, hideLabel, center, centerNote, slices }: Props) {
  const patternId = useId();
  const total = slices.reduce((sum, s) => sum + s.count, 0);
  const summary = slices.map((s) => `${s.label} ${percentOf(s.count, total)}%`).join(', ');
  let offset = 0;
  return (
    <figure className="chart donut">
      <figcaption className={hideLabel ? 'chart-label chart-label-hidden' : 'chart-label'}>{label}</figcaption>
      <div className="donut-body">
        <div className="donut-ring">
          <svg viewBox={`0 0 ${VIEW} ${VIEW}`} role="img" aria-label={summary}>
            <defs>
              <pattern id={patternId} width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="4" height="4" className="stripe-base" />
                <rect width="2" height="4" className="stripe-line" />
              </pattern>
            </defs>
            <circle className="donut-track" cx={CENTER} cy={CENTER} r={RADIUS} fill="none" strokeWidth={STROKE} />
            {total > 0
              ? slices.map((s) => {
                  const length = (s.count / total) * 100;
                  const start = offset;
                  offset += length;
                  if (s.count === 0) return null;
                  return (
                    <circle
                      key={s.label}
                      className={`donut-slice ${toneClass(s.tone)}`}
                      cx={CENTER}
                      cy={CENTER}
                      r={RADIUS}
                      fill="none"
                      strokeWidth={STROKE}
                      strokeDasharray={`${length} ${100 - length}`}
                      strokeDashoffset={25 - start}
                      stroke={s.tone === 'negative' ? `url(#${patternId})` : undefined}
                      style={s.tone === 'negative' ? { stroke: `url(#${patternId}) var(--color-chart-negative)` } : undefined}
                    >
                      <title>{`${s.label}: ${plural(s.count, 'answer', 'answers')}, ${percentOf(s.count, total)}%`}</title>
                    </circle>
                  );
                })
              : null}
          </svg>
          <div className="donut-center">
            <strong>{center}</strong>
            <span>{centerNote}</span>
          </div>
        </div>
        <ul className="chart-legend">
          {slices.map((s) => (
            <li key={s.label}>
              <i className={`chart-swatch ${toneClass(s.tone)}`} aria-hidden="true" />
              <span className="chart-legend-label">{s.label}</span>
              <strong>{percentOf(s.count, total)}%</strong>
              <span className="chart-legend-count">{s.count}</span>
            </li>
          ))}
        </ul>
      </div>
    </figure>
  );
}
