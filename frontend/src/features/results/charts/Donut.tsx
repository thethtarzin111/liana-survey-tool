import { useId } from 'react';
import { plural } from '../format';
import { percentOf, toneClass, type Tone } from './tone';

export type DonutSlice = { label: string; count: number; tone: Tone };

type Props = { label: string; center: string; centerNote: string; slices: DonutSlice[] };

const RADIUS = 15.9155; // circumference 100, so a dash length is a percentage

/** A ring split into slices, with the headline number in the middle and a legend beside it. */
export function Donut({ label, center, centerNote, slices }: Props) {
  const patternId = useId();
  const total = slices.reduce((sum, s) => sum + s.count, 0);
  const summary = slices.map((s) => `${s.label} ${percentOf(s.count, total)}%`).join(', ');
  let offset = 0;
  return (
    <figure className="chart donut">
      <figcaption className="chart-label">{label}</figcaption>
      <div className="donut-body">
        <div className="donut-ring">
          <svg viewBox="0 0 36 36" role="img" aria-label={summary}>
            <defs>
              <pattern id={patternId} width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="4" height="4" className="stripe-base" />
                <rect width="2" height="4" className="stripe-line" />
              </pattern>
            </defs>
            <circle className="donut-track" cx="18" cy="18" r={RADIUS} fill="none" strokeWidth="5" />
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
                      cx="18"
                      cy="18"
                      r={RADIUS}
                      fill="none"
                      strokeWidth="5"
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
