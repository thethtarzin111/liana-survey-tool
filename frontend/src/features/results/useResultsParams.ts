import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

export type ResultsTab = 'overview' | 'responses' | 'insights';
const TABS: ResultsTab[] = ['overview', 'responses', 'insights'];
export type ResultsChanges = Partial<{ survey: string; tab: ResultsTab; segment: string; q: string; group: string }>;

/**
 * The Results page's view, kept in the URL (`survey`, `tab`, `segment`, `q`, `group`) so a reload
 * or a shared link opens the same view. Choosing another survey resets the segment, search and answer group.
 */
export function useResultsParams() {
  const [params, setParams] = useSearchParams();
  const survey = params.get('survey') || null;
  const tab: ResultsTab = TABS.find((t) => t === params.get('tab')) ?? 'overview';
  const segment = params.get('segment') || 'all';
  const q = params.get('q') || '';
  const group = params.get('group') || '';

  const set = useCallback(
    (changes: ResultsChanges, options: { replace?: boolean } = {}) => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        const apply = (key: string, value: string | undefined, empty: string) => {
          if (value === undefined) return;
          if (value === empty) next.delete(key);
          else next.set(key, value);
        };
        if (changes.survey !== undefined && changes.survey !== current.get('survey')) {
          next.delete('segment');
          next.delete('q');
          next.delete('group');
        }
        apply('survey', changes.survey, '');
        apply('tab', changes.tab, 'overview');
        apply('segment', changes.segment, 'all');
        apply('q', changes.q, '');
        apply('group', changes.group, '');
        return next;
      }, { replace: options.replace });
    },
    [setParams],
  );

  return { survey, tab, segment, q, group, set };
}
