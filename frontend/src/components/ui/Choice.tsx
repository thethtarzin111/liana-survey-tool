import type { ReactNode } from 'react';
import { IconCircle } from './EmptyState';

export type SegmentOption = { value: string; label: ReactNode };

type SegmentedProps = {
  label: string;
  options: SegmentOption[];
  value: string;
  onChange: (value: string) => void;
};

/** Grey pill group where one option is on, e.g. the "All / Live / Draft" filter. */
export function SegmentedControl({ label, options, value, onChange }: SegmentedProps) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className="segment"
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export type Step = { id: string; label: string };

type StepperProps = {
  steps: Step[];
  /** Id of the current step. Earlier steps are done and can be revisited. */
  current: string;
  onSelect?: (id: string) => void;
  label?: string;
};

/** Wizard steps: done (tick), current (green number), future (disabled). */
export function Stepper({ steps, current, onSelect, label = 'Steps' }: StepperProps) {
  const at = steps.findIndex((s) => s.id === current);
  return (
    <ol className="stepper" aria-label={label}>
      {steps.map((s, i) => {
        const state = i < at ? 'done' : i === at ? 'current' : 'future';
        return (
          <li key={s.id}>
            <button
              type="button"
              className={`step step-${state}`}
              disabled={state === 'future'}
              aria-current={state === 'current' ? 'step' : undefined}
              onClick={() => onSelect?.(s.id)}
            >
              <span className="step-n" aria-hidden="true">
                {state === 'done' ? '✓' : i + 1}
              </span>
              {s.label}
              {state === 'done' ? <span className="visually-hidden"> (done)</span> : null}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

type OptionCardProps = {
  title: ReactNode;
  description?: ReactNode;
  /** Icon path shown in a mint circle at the top. */
  icon?: string;
  /** Set for pick-one cards; leave undefined for cards that just navigate. */
  selected?: boolean;
  onClick: () => void;
  children?: ReactNode;
};

/** Big clickable card, e.g. the survey type picker ("Thumbs rating", "NPS"…). */
export function OptionCard({ title, description, icon, selected, onClick, children }: OptionCardProps) {
  return (
    <button type="button" className="option-card" aria-pressed={selected} onClick={onClick}>
      {icon ? <IconCircle icon={icon} size={48} /> : null}
      <span className="option-title">{title}</span>
      {description ? <span className="option-text">{description}</span> : null}
      {children}
    </button>
  );
}

/** Thin progress bar. `label` names what it measures, e.g. "Responses toward the limit". */
export function ProgressBar({ value, max = 100, label }: { value: number; max?: number; label: string }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div
      className="progress"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
    >
      <div className="progress-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

/** Small grey heading with a line after it, splitting a form into parts. */
export function SectionHeader({ children, level = 3 }: { children: ReactNode; level?: 2 | 3 | 4 }) {
  const H = `h${level}` as 'h2' | 'h3' | 'h4';
  return <H className="section-header">{children}</H>;
}

/** Rows with a line between them, inside a card. */
export function List({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <ul className="list" aria-label={label}>
      {children}
    </ul>
  );
}

export function ListItem({ children }: { children: ReactNode }) {
  return <li className="list-item">{children}</li>;
}

