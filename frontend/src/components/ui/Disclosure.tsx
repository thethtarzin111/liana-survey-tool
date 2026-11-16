import { useId, useState, type ReactNode } from 'react';
import { Icon } from '../Icon';
import { icons } from './icons';

type DisclosureProps = {
  title: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  /** Controlled mode: pass both. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

/** Section that opens and closes, e.g. "Branding" or "Advanced settings". */
export function Disclosure({ title, children, defaultOpen = false, open, onOpenChange }: DisclosureProps) {
  const id = useId();
  const [inner, setInner] = useState(defaultOpen);
  const isOpen = open ?? inner;
  const toggle = () => {
    setInner(!isOpen);
    onOpenChange?.(!isOpen);
  };
  return (
    <div>
      <button type="button" className="disclosure-button" aria-expanded={isOpen} aria-controls={id} onClick={toggle}>
        {title}
        <span className="disclosure-chevron" aria-hidden="true">
          <Icon path={icons.chevronDown} size={18} />
        </span>
      </button>
      <div id={id} className="disclosure-panel" hidden={!isOpen}>
        {children}
      </div>
    </div>
  );
}

/** Text that is only read by screen readers. */
export function VisuallyHidden({ children }: { children: ReactNode }) {
  return <span className="visually-hidden">{children}</span>;
}
