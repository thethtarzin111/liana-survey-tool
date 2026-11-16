import type { ReactNode } from 'react';
import { Icon } from '../Icon';

/** Mint circle with a green icon (empty states, front page tiles). */
export function IconCircle({ icon, size = 60 }: { icon: string; size?: number }) {
  return (
    <span className="icon-circle" aria-hidden="true" style={{ width: size, height: size }}>
      <Icon path={icon} size={Math.round(size * 0.46)} strokeWidth={1.6} />
    </span>
  );
}

type Props = {
  icon: string;
  title: string;
  text?: ReactNode;
  /** Buttons, e.g. "+ Create survey" and "Browse templates". */
  actions?: ReactNode;
};

/** Shown instead of a list or chart when there is nothing yet. */
export function EmptyState({ icon, title, text, actions }: Props) {
  return (
    <div className="empty-state">
      <IconCircle icon={icon} />
      <p className="empty-title">{title}</p>
      {text ? <p className="empty-text">{text}</p> : null}
      {actions ? <div className="empty-actions">{actions}</div> : null}
    </div>
  );
}
