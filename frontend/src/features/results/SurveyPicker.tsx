import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import type { SurveyListItem } from '../../api/client';
import { Icon } from '../../components/Icon';
import { SurveyStatusBadge, icons } from '../../components/ui';
import { TYPE_LABEL, plural } from './format';

const STATUS_TEXT = { draft: 'Draft', scheduled: 'Scheduled', live: 'Live', closed: 'Closed' } as const;

type Props = {
  surveys: SurveyListItem[];
  /** The chosen survey's id; null when the URL names a survey that does not exist. */
  value: string | null;
  onPick: (id: string) => void;
  /** Smaller, for the tab row: the "Survey" label is for screen readers only. */
  compact?: boolean;
};

/**
 * A button with the chosen survey that opens a searchable list. Focus is in the search
 * field while the list is open: arrow keys move, Enter picks, Escape closes.
 */
export function SurveyPicker({ surveys, value, onPick, compact = false }: Props) {
  const base = useId();
  const labelId = `${base}-label`;
  const listId = `${base}-list`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const button = useRef<HTMLButtonElement>(null);
  const search = useRef<HTMLInputElement>(null);

  const chosen = surveys.find((s) => s.id === value) ?? null;
  const needle = query.trim().toLowerCase();
  const shown = needle ? surveys.filter((s) => s.title.toLowerCase().includes(needle)) : surveys;
  const current = Math.min(active, Math.max(0, shown.length - 1));

  useEffect(() => {
    if (open) search.current?.focus();
  }, [open]);

  // Keep the highlighted option inside the scrolling list.
  const activeId = open && shown[current] ? `${base}-opt-${shown[current].id}` : null;
  useEffect(() => {
    if (activeId) document.getElementById(activeId)?.scrollIntoView?.({ block: 'nearest' });
  }, [activeId]);

  function toggle() {
    if (!open) {
      setQuery('');
      setActive(Math.max(0, surveys.findIndex((s) => s.id === value)));
    }
    setOpen(!open);
  }

  function close(refocus: boolean) {
    setOpen(false);
    if (refocus) button.current?.focus();
  }

  function pick(survey: SurveyListItem) {
    onPick(survey.id);
    close(true);
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (shown.length === 0) return;
      const step = e.key === 'ArrowDown' ? 1 : -1;
      setActive((current + step + shown.length) % shown.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (shown[current]) pick(shown[current]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close(true);
    }
  }

  return (
    <div
      className={compact ? 'results-picker results-picker-compact' : 'results-picker'}
      onBlur={(e) => {
        if (open && !e.currentTarget.contains(e.relatedTarget)) close(false);
      }}
    >
      <span id={labelId} className={compact ? 'results-picker-label visually-hidden' : 'results-picker-label'}>
        Survey
      </span>
      <button
        ref={button}
        type="button"
        className="results-picker-button"
        aria-labelledby={`${labelId} ${base}-value`}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={toggle}
      >
        <span id={`${base}-value`} className="results-picker-value">
          <strong>{chosen ? chosen.title : 'Choose a survey'}</strong>
          {chosen ? <small>{TYPE_LABEL[chosen.type]} · {STATUS_TEXT[chosen.status]}</small> : null}
        </span>
        <Icon path={icons.chevronDown} size={16} />
      </button>
      {open ? (
        <div className="results-picker-panel" role="dialog" aria-label="Choose a survey">
          <input
            ref={search}
            type="search"
            className="input"
            placeholder="Search surveys..."
            role="combobox"
            aria-label="Search surveys"
            aria-expanded="true"
            aria-autocomplete="list"
            aria-controls={listId}
            aria-activedescendant={activeId ?? undefined}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKey}
          />
          <ul id={listId} role="listbox" aria-label="Surveys" className="results-picker-list">
            {shown.map((survey, i) => (
              <li
                key={survey.id}
                id={`${base}-opt-${survey.id}`}
                role="option"
                aria-selected={survey.id === value}
                className={i === current ? 'active' : undefined}
                // Keep focus in the search field when clicking.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(survey)}
              >
                <span className="results-picker-name">
                  <strong>{survey.title}</strong>
                  <small>{TYPE_LABEL[survey.type]} · {plural(survey.answers, 'answer', 'answers')}</small>
                </span>
                <SurveyStatusBadge status={survey.status} />
                <span className="results-picker-tick" aria-hidden="true">
                  {survey.id === value ? <Icon path={icons.check} size={14} strokeWidth={2.4} /> : null}
                </span>
              </li>
            ))}
          </ul>
          {shown.length === 0 ? <p className="results-picker-none">No surveys match “{query.trim()}”.</p> : null}
        </div>
      ) : null}
    </div>
  );
}
