import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

export type ResultsTab = 'overview' | 'responses';
export type ResultsChanges = Partial<{ survey: string; tab: ResultsTab; segment: string }>;

/**
 * The Results page's view, kept in the URL (`survey`, `tab`, `segment`) so a reload
 * or a shared link opens the same view. Choosing another survey resets the segment.
 */
export function useResultsParams() {
  const [params, setParams] = useSearchParams();
  const survey = params.get('survey') || null;
  const tab: ResultsTab = params.get('tab') === 'responses' ? 'responses' : 'overview';
  const segment = params.get('segment') || 'all';

  const set = useCallback(
    (changes: ResultsChanges) => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        const apply = (key: string, value: string | undefined, empty: string) => {
          if (value === undefined) return;
          if (value === empty) next.delete(key);
          else next.set(key, value);
        };
        if (changes.survey !== undefined && changes.survey !== current.get('survey')) next.delete('segment');
        apply('survey', changes.survey, '');
        apply('tab', changes.tab, 'overview');
        apply('segment', changes.segment, 'all');
        return next;
      });
    },
    [setParams],
  );

  return { survey, tab, segment, set };
}
