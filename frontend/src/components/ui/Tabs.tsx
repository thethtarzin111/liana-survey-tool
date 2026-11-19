import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react';

export type TabItem = { id: string; label: ReactNode };

type TabsProps = {
  label: string;
  tabs: TabItem[];
  value: string;
  onChange: (id: string) => void;
  /** Shown at the right end of the tab row, e.g. a filter that applies to every tab. */
  actions?: ReactNode;
  /** Extra class on the outer element. */
  className?: string;
  /** The panel for the selected tab. */
  children: ReactNode;
};

/**
 * Tabs with the WAI-ARIA keyboard pattern: arrow keys move between tabs,
 * Home/End jump to the first/last, only the selected tab is in the tab order.
 */
export function Tabs({ label, tabs, value, onChange, actions, className, children }: TabsProps) {
  const base = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const current = Math.max(
    0,
    tabs.findIndex((t) => t.id === value),
  );

  const onKey = (e: KeyboardEvent) => {
    const last = tabs.length - 1;
    const next = { ArrowRight: current + 1, ArrowLeft: current - 1, Home: 0, End: last }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    const i = (next + tabs.length) % tabs.length;
    onChange(tabs[i].id);
    refs.current[i]?.focus();
  };

  const list = (
    <div role="tablist" aria-label={label} className="tabs" onKeyDown={onKey}>
      {tabs.map((t, i) => (
        <button
          key={t.id}
          ref={(el) => {
            refs.current[i] = el;
          }}
          type="button"
          role="tab"
          id={`${base}-tab-${t.id}`}
          aria-selected={t.id === value}
          aria-controls={`${base}-panel`}
          tabIndex={t.id === value ? 0 : -1}
          className="tab"
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className={className}>
      {actions ? (
        <div className="tabs-row">
          {list}
          {actions}
        </div>
      ) : (
        list
      )}
      <div role="tabpanel" id={`${base}-panel`} aria-labelledby={`${base}-tab-${tabs[current]?.id}`} tabIndex={0}>
        {children}
      </div>
    </div>
  );
}
