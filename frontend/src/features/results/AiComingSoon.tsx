import type { ReactNode } from 'react';
import { Card } from '../../components/ui';

/** A placeholder where the AI summary will go. It makes no request. */
export function AiComingSoon() {
  return (
    <Card className="results-card results-ai">
      <h3 className="results-card-title">AI summary of comments</h3>
      <p className="results-ai-text">
        AI summary of comments is coming soon. It will group comments into themes.
      </p>
    </Card>
  );
}

/** The AI placeholder beside a companion card (3 : 2); it spans the row when there is none. */
export function AiRow({ children }: { children?: ReactNode }) {
  return (
    <div className={['results-row', 'results-row-ai', children ? '' : 'results-row-solo'].filter(Boolean).join(' ')}>
      <AiComingSoon />
      {children}
    </div>
  );
}
