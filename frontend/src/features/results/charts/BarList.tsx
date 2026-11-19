import { plural } from '../format';

export type BarRow = { label: string; count: number; percent: number };

type Props = { label: string; rows: BarRow[]; note?: string };

/** Horizontal bars with the label, share and count of each row. */
export function BarList({ label, rows, note }: Props) {
  const summary = rows.map((r) => `${r.label} ${r.percent}%`).join(', ');
  return (
    <figure className="chart barlist">
      <figcaption className="chart-label">{label}</figcaption>
      <ul className="barlist-rows" role="img" aria-label={summary}>
        {rows.map((r) => (
          <li
            key={r.label}
            className="barlist-row"
            title={`${r.label}: ${plural(r.count, 'answer', 'answers')}, ${r.percent}%`}
          >
            <span className="barlist-label">{r.label}</span>
            <span className="barlist-track">
              <span className="barlist-bar" style={{ width: `${Math.min(100, r.percent)}%` }} />
            </span>
            <strong className="barlist-percent">{r.percent}%</strong>
            <span className="barlist-count">{r.count}</span>
          </li>
        ))}
      </ul>
      {note ? <figcaption className="chart-note">{note}</figcaption> : null}
    </figure>
  );
}
