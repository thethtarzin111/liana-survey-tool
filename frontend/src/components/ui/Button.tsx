import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Link, type LinkProps } from 'react-router-dom';
import { Icon } from '../Icon';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'dark' | 'danger';

type StyleProps = {
  variant?: ButtonVariant;
  size?: 'md' | 'sm';
  /** Full width (e.g. the sidebar's Create survey button). */
  block?: boolean;
  /** Icon path (24x24 viewBox) shown before the label. */
  icon?: string;
};

function classes({ variant = 'secondary', size = 'md', block }: StyleProps, extra?: string) {
  return ['btn', `btn-${variant}`, size === 'sm' && 'btn-sm', block && 'btn-block', extra]
    .filter(Boolean)
    .join(' ');
}

type ButtonProps = StyleProps &
  ButtonHTMLAttributes<HTMLButtonElement> & {
    /** Shows a spinner, disables the button and tells screen readers it is busy. */
    loading?: boolean;
  };

/** Pill button. Defaults to type="button" so it never submits a form by accident. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant, size, block, icon, loading, disabled, className, children, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={classes({ variant, size, block }, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <span className="btn-spinner" aria-hidden="true" /> : icon ? <Icon path={icon} size={16} /> : null}
      {children}
    </button>
  );
});

/** A router link that looks like a button (for navigation, not actions). */
export function ButtonLink({
  variant,
  size,
  block,
  icon,
  className,
  children,
  ...rest
}: StyleProps & LinkProps & { children: ReactNode }) {
  return (
    <Link className={classes({ variant, size, block }, className)} {...rest}>
      {icon ? <Icon path={icon} size={16} /> : null}
      {children}
    </Link>
  );
}

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** Required: icon-only buttons need a name for screen readers. */
  label: string;
  icon: string;
  iconSize?: number;
};

/** Round icon-only button (34 px). */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, iconSize = 18, className, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={['icon-button', className].filter(Boolean).join(' ')}
      aria-label={label}
      title={label}
      {...rest}
    >
      <Icon path={icon} size={iconSize} />
    </button>
  );
});

/** Inline green text action, like a link but for buttons ("View all", "Undo"). */
export function TextButton({ className, type = 'button', ...rest }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type={type} className={['text-button', className].filter(Boolean).join(' ')} {...rest} />;
}
