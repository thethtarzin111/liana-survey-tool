import type { HTMLAttributes, ReactNode } from 'react';

type CardProps = HTMLAttributes<HTMLElement> & {
  /** Adds 20 px padding. Leave off when the card has a CardHeader, list or table inside. */
  padded?: boolean;
  as?: 'section' | 'div' | 'article';
};

/** White box with Liana's border, radius and shadow. */
export function Card({ padded, as: Tag = 'section', className, ...rest }: CardProps) {
  return <Tag className={['card', padded && 'card-padded', className].filter(Boolean).join(' ')} {...rest} />;
}

type HeaderProps = {
  title: ReactNode;
  /** Buttons or links on the right, e.g. "View all". */
  actions?: ReactNode;
  /** Heading level for the title, so the page outline stays right. */
  level?: 2 | 3;
  id?: string;
};

/** Title row at the top of a card, with a line under it. */
export function CardHeader({ title, actions, level = 2, id }: HeaderProps) {
  const H = level === 2 ? 'h2' : 'h3';
  return (
    <div className="card-header">
      <H className="card-title" id={id}>
        {title}
      </H>
      {actions ? <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>{actions}</div> : null}
    </div>
  );
}

export function CardBody({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={['card-body', className].filter(Boolean).join(' ')} {...rest} />;
}
