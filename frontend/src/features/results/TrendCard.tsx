import { Card, CardBody, CardHeader } from '../../components/ui';
import { signed } from './format';

type Kind = 'nps' | 'thumbs' | 'rating';
type Point = { month: string; score: number | null; answers: number };

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const W = 640;
const H = 214;
const LEFT = 48;
const RIGHT = 616;
const TOP = 28;
const BOTTOM = 170;

/** "2026-11" is "Nov". */
const monthName = (month: string) => MONTHS[Number(month.slice(5, 7)) - 1] ?? month;
const valueText = (kind: Kind, score: number) => (kind === 'nps' ? signed(score) : `${score}%`);

/** The main score by calendar month as a line; hidden until two months have answers. */
export function TrendCard({ kind, trend }: { kind: Kind; trend: Point[] }) {
  if (trend.length < 2) return null;
  const [min, max] = kind === 'nps' ? [-100, 100] : [0, 100];
  const x = (i: number) => LEFT + (i * (RIGHT - LEFT)) / (trend.length - 1);
  const y = (score: number) => BOTTOM - ((score - min) / (max - min)) * (BOTTOM - TOP);
  const shown = trend.flatMap((p, i) => (p.score === null ? [] : [{ ...p, score: p.score, i }]));
  const line = shown.map((p) => `${x(p.i)},${y(p.score)}`).join(' ');
  const grid = [max, (min + max) / 2, min];
  const summary = `Score by month: ${trend
    .map((p) => `${monthName(p.month)} ${p.score === null ? 'no score' : valueText(kind, p.score)}`)
    .join(', ')}`;
  return (
    <Card>
      <CardHeader title="Trend" />
      <CardBody>
        <svg className="trend" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}>
          {grid.map((g) => (
            <g key={g}>
              <line className="trend-grid" x1={LEFT} x2={RIGHT} y1={y(g)} y2={y(g)} />
              <text className="trend-axis" x={LEFT - 8} y={y(g) + 4} textAnchor="end">
                {valueText(kind, g)}
              </text>
            </g>
          ))}
          <polyline className="trend-line" points={line} />
          {shown.map((p) => (
            <g key={p.month}>
              <circle className="trend-dot" cx={x(p.i)} cy={y(p.score)} r={5}>
                <title>{`${monthName(p.month)}: ${valueText(kind, p.score)}, ${p.answers} answers`}</title>
              </circle>
              <text className="trend-value" x={x(p.i)} y={y(p.score) - 12} textAnchor="middle">
                {valueText(kind, p.score)}
              </text>
            </g>
          ))}
          {trend.map((p, i) => (
            <text key={p.month} className="trend-axis" x={x(i)} y={H - 16} textAnchor="middle">
              {monthName(p.month)}
            </text>
          ))}
        </svg>
      </CardBody>
    </Card>
  );
}
