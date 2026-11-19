import type { SurveyOverview } from '../../api/client';
import { percentOf } from './charts/tone';
import { RATING_GROUPS } from './groups';

/** One sentence about the first rating question, built by rules from the counts. */
export function takeaway(overview: SurveyOverview): string | null {
  const q = overview.questions.find((item) => item.kind === 'rating');
  if (!q) return null;
  const total = q.options.reduce((sum, o) => sum + o.count, 0);
  if (total === 0) return null;
  const high = q.options
    .filter((o) => RATING_GROUPS[2].values.includes(o.label))
    .reduce((sum, o) => sum + o.count, 0);
  const share = percentOf(high, total);
  return share >= 50
    ? `“${q.prompt}”: most respondents rated it 4–5 (${share}%).`
    : `“${q.prompt}”: ratings are mixed, ${share}% gave 4–5.`;
}
