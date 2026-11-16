import { useId, useState, type ReactNode } from 'react';
import { Icon } from '../Icon';
import { icons } from './icons';

/**
 * (i) button that shows a short explanation on hover, focus or tap.
 * The text is linked with aria-describedby, so screen readers read it too.
 * Escape hides it.
 */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  return (
    <span className={open ? 'tip tip-open' : 'tip'}>
      <button
        type="button"
        className="tip-button"
        aria-label={label}
        aria-describedby={id}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setOpen(false);
        }}
      >
        <Icon path={icons.info} size={16} />
      </button>
      <span role="tooltip" id={id} className="tip-text">
        {children}
      </span>
    </span>
  );
}
