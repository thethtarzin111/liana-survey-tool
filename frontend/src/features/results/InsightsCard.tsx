import { Button, Card } from '../../components/ui';

/** Points to the Comment insights tab. It makes no request. */
export function InsightsCard({ onOpen }: { onOpen: () => void }) {
  return (
    <Card className="results-card results-ai results-loop">
      <div className="results-loop-text">
        <h3 className="results-card-title">Comment insights</h3>
        <p className="results-ai-text">AI groups the comments into themes, with quotes and the sentiment of each.</p>
      </div>
      <Button onClick={onOpen}>Open Comment insights</Button>
    </Card>
  );
}
