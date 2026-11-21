import { useId, type ReactNode } from 'react';

type SwitchProps = {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** A line under the label explaining what the switch does. */
  description?: ReactNode;
  disabled?: boolean;
};

/** An on/off switch (role="switch") with its label and an optional description. */
export function Switch({ label, checked, onChange, description, disabled }: SwitchProps) {
  const id = useId();
  return (
    <div className="switch-row">
      <span className="switch-text">
        <span className="switch-label" id={`${id}-label`}>
          {label}
        </span>
        {description ? (
          <span className="switch-description" id={`${id}-description`}>
            {description}
          </span>
        ) : null}
      </span>
      <button
        type="button"
        role="switch"
        className="switch"
        aria-checked={checked}
        aria-labelledby={`${id}-label`}
        aria-describedby={description ? `${id}-description` : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
      >
        <span className="switch-knob" aria-hidden="true" />
      </button>
    </div>
  );
}
