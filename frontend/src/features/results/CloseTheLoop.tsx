import type { SurveyOverview } from '../../api/client';
import { ButtonLink, Card } from '../../components/ui';

const TEXT: Record<'thumbs' | 'nps' | 'csat', string> = {
  thumbs: 'Reply to readers who chose “Not for me” and ask what to improve.',
  nps: 'Reply to detractors (0–6) and ask what went wrong.',
  csat: 'Reply to people who were unsatisfied (1–2) and offer a call back.',
};

/** Standard surveys: a pointer to the people who asked to be contacted. */
export function CloseTheLoop({ type }: { type: SurveyOverview['type'] }) {
  if (type === 'custom') return null;
  return (
    <Card className="results-card results-loop">
      <div className="results-loop-text">
        <h2 className="results-loop-title">Close the loop</h2>
        <p className="results-loop-note">{TEXT[type]}</p>
      </div>
      <ButtonLink variant="secondary" size="sm" to="/contact-requests">Open contact requests</ButtonLink>
    </Card>
  );
}
