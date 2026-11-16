import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react';
import { IconButton } from './Button';
import { icons } from './icons';

type FieldProps = {
  label: ReactNode;
  /** Short help under the label. */
  hint?: ReactNode;
  /** Error message; also marks the control invalid for screen readers. */
  error?: ReactNode;
  required?: boolean;
  /** Hide the label visually (it is still read out). */
  hideLabel?: boolean;
};

/** Ids that link a control to its label, hint and error. */
function useFieldIds(id?: string) {
  const auto = useId();
  const base = id ?? auto;
  return { id: base, hintId: `${base}-hint`, errorId: `${base}-error` };
}

function describedBy(hint: ReactNode, error: ReactNode, ids: { hintId: string; errorId: string }) {
  return [hint && ids.hintId, error && ids.errorId].filter(Boolean).join(' ') || undefined;
}

function FieldShell({
  label,
  hint,
  error,
  required,
  hideLabel,
  ids,
  children,
}: FieldProps & { ids: ReturnType<typeof useFieldIds>; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={ids.id} className={hideLabel ? 'visually-hidden' : 'field-label'}>
        {label}
        {required ? (
          <span className="field-required" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {hint ? (
        <p className="field-hint" id={ids.hintId}>
          {hint}
        </p>
      ) : null}
      {children}
      {error ? (
        <p className="field-error" id={ids.errorId} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

type TextFieldProps = FieldProps & Omit<InputHTMLAttributes<HTMLInputElement>, 'required'>;

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hint, error, required, hideLabel, id, className, ...rest },
  ref,
) {
  const ids = useFieldIds(id);
  return (
    <FieldShell {...{ label, hint, error, required, hideLabel, ids }}>
      <input
        ref={ref}
        id={ids.id}
        className={['input', className].filter(Boolean).join(' ')}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(hint, error, ids)}
        {...rest}
      />
    </FieldShell>
  );
});

type TextAreaProps = FieldProps & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'required'>;

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea(
  { label, hint, error, required, hideLabel, id, className, rows = 3, ...rest },
  ref,
) {
  const ids = useFieldIds(id);
  return (
    <FieldShell {...{ label, hint, error, required, hideLabel, ids }}>
      <textarea
        ref={ref}
        id={ids.id}
        rows={rows}
        className={['input', className].filter(Boolean).join(' ')}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(hint, error, ids)}
        {...rest}
      />
    </FieldShell>
  );
});

export type SelectOption = { value: string; label: string };

type SelectProps = FieldProps &
  Omit<SelectHTMLAttributes<HTMLSelectElement>, 'required'> & { options: SelectOption[] };

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, required, hideLabel, id, className, options, ...rest },
  ref,
) {
  const ids = useFieldIds(id);
  return (
    <FieldShell {...{ label, hint, error, required, hideLabel, ids }}>
      <select
        ref={ref}
        id={ids.id}
        className={['input', className].filter(Boolean).join(' ')}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(hint, error, ids)}
        {...rest}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
});

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  label: ReactNode;
  /** Extra line under the label. */
  hint?: ReactNode;
};

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, hint, className, ...rest },
  ref,
) {
  return (
    <label className={['check', className].filter(Boolean).join(' ')}>
      <input ref={ref} type="checkbox" {...rest} />
      <span>
        {label}
        {hint ? <span className="check-hint">{hint}</span> : null}
      </span>
    </label>
  );
});

export type RadioOption = { value: string; label: ReactNode; hint?: ReactNode; disabled?: boolean };

type RadioGroupProps = {
  legend: ReactNode;
  name: string;
  options: RadioOption[];
  value: string;
  onChange: (value: string) => void;
  hideLegend?: boolean;
};

/** A set of radio buttons in a fieldset, e.g. Anonymous / Identified. */
export function RadioGroup({ legend, name, options, value, onChange, hideLegend }: RadioGroupProps) {
  return (
    <fieldset className="radio-group">
      <legend className={hideLegend ? 'visually-hidden' : 'field-label'}>{legend}</legend>
      {options.map((o) => (
        <label key={o.value} className="check">
          <input
            type="radio"
            name={name}
            value={o.value}
            checked={value === o.value}
            disabled={o.disabled}
            onChange={() => onChange(o.value)}
          />
          <span>
            {o.label}
            {o.hint ? <span className="check-hint">{o.hint}</span> : null}
          </span>
        </label>
      ))}
    </fieldset>
  );
}

type SearchProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Runs on Enter or the search button. */
  onSearch?: (value: string) => void;
  placeholder?: string;
};

/** Search box with a search button, as in the sidebar. */
export function SearchInput({ label, value, onChange, onSearch, placeholder = 'Search...' }: SearchProps) {
  const id = useId();
  return (
    <div className="search" role="search">
      <label htmlFor={id} className="visually-hidden">
        {label}
      </label>
      <input
        id={id}
        type="search"
        className="input"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onSearch?.(value);
        }}
      />
      <IconButton label={label} icon={icons.search} iconSize={16} onClick={() => onSearch?.(value)} />
    </div>
  );
}
