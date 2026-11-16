import { useId, useState, type ButtonHTMLAttributes, type ReactNode } from 'react';

type ToggleChipProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'> & {
  selected: boolean;
  onChange: (selected: boolean) => void;
};

/** Pill that is on or off, e.g. answer reasons a reader can pick. */
export function ToggleChip({ selected, onChange, className, children, ...rest }: ToggleChipProps) {
  return (
    <button
      type="button"
      className={['chip', className].filter(Boolean).join(' ')}
      aria-pressed={selected}
      onClick={() => onChange(!selected)}
      {...rest}
    >
      {children}
    </button>
  );
}

type EditableChipProps = {
  value: string;
  onChange: (value: string) => void;
  onRemove: () => void;
  /** Accessible name, e.g. "Reason 2". */
  label: string;
};

/** Chip whose text can be edited in place, with a remove button. */
export function EditableChip({ value, onChange, onRemove, label }: EditableChipProps) {
  return (
    <span className="chip-edit">
      <input
        aria-label={label}
        value={value}
        size={Math.max(3, value.length)}
        onChange={(e) => onChange(e.target.value)}
      />
      <button type="button" className="chip-remove" aria-label={`Remove ${label}`} onClick={onRemove}>
        ×
      </button>
    </span>
  );
}

/** Small grey label (Fomantic "ui label"), optionally removable. */
export function Tag({ children, onRemove, removeLabel }: { children: ReactNode; onRemove?: () => void; removeLabel?: string }) {
  return (
    <span className="tag">
      {children}
      {onRemove ? (
        <button type="button" className="chip-remove" aria-label={removeLabel ?? 'Remove'} onClick={onRemove}>
          ×
        </button>
      ) : null}
    </span>
  );
}

type TagInputProps = {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  hint?: ReactNode;
};

/** Box with tags inside; Enter or comma adds, Backspace on empty removes the last. */
export function TagInput({ label, values, onChange, placeholder = 'Add…', hint }: TagInputProps) {
  const id = useId();
  const [draft, setDraft] = useState('');

  const add = () => {
    const v = draft.trim();
    if (v && !values.includes(v)) onChange([...values, v]);
    setDraft('');
  };

  return (
    <div className="field">
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      {hint ? (
        <p className="field-hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
      <div className="tag-input">
        {values.map((v) => (
          <Tag key={v} onRemove={() => onChange(values.filter((x) => x !== v))} removeLabel={`Remove ${v}`}>
            {v}
          </Tag>
        ))}
        <input
          id={id}
          value={draft}
          placeholder={placeholder}
          aria-describedby={hint ? `${id}-hint` : undefined}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={add}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') {
              e.preventDefault();
              add();
            } else if (e.key === 'Backspace' && !draft && values.length) {
              onChange(values.slice(0, -1));
            }
          }}
        />
      </div>
    </div>
  );
}
