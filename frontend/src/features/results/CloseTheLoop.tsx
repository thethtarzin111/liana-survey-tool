import type { SurveyOverview } from '../../api/client';
import { Button, Card } from '../../components/ui';
import { useResultsParams } from './useResultsParams';

const TEXT: Record<'thumbs' | 'nps' | 'csat', string> = {
  thumbs: 'Reply to readers who chose “Not for me” and ask what to improve.',
  nps: 'Reply to detractors (0–6) and ask what went wrong.',
  csat: 'Reply to people who were unsatisfied (1–2) and offer a call back.',
};

/** Standard surveys: a pointer to the people who asked to be contacted. */
export function CloseTheLoop({ type }: { type: SurveyOverview['type'] }) {
  const { set } = useResultsParams();
  if (type === 'custom') return null;
  return (
    <Card className="results-card results-loop">
      <div className="results-loop-text">
        <h2 className="results-loop-title">Close the loop</h2>
        <p className="results-loop-note">
          {TEXT[type]} Readers who tick “Contact me” are listed in Responses with their email address, and sent to
          LianaAutomation.
        </p>
      </div>
      <Button variant="secondary" size="sm" onClick={() => set({ tab: 'responses', group: 'contact' })}>
        Open contact requests
      </Button>
    </Card>
  );
}
