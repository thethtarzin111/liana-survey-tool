import { Fragment, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { Icon } from '../Icon';
import { IconButton } from './Button';
import { icons } from './icons';

export type MenuAction = {
  label: string;
  /** What the item does. Items with `href` are links and need none. */
  onSelect?: () => void;
  /** Makes the item a link, e.g. to another Liana app. */
  href?: string;
  icon?: string;
  /** Larger picture before the label, e.g. an app icon. Used instead of `icon`. */
  media?: ReactNode;
  /** Red text, for Delete and similar. */
  danger?: boolean;
  /** Marks the current item (aria-current), e.g. the app you are in. */
  current?: boolean;
  /** A heading shown above this item, starting a new group. */
  heading?: string;
};

type ActionMenuProps = {
  /** Name of the button and the menu, e.g. "Actions for Member NPS 2026". */
  label: string;
  items: MenuAction[];
  /** Custom trigger icon; defaults to ⋯. */
  icon?: string;
  /** Content of a custom trigger button (e.g. an avatar and a name) instead of an icon. */
  trigger?: ReactNode;
  triggerClassName?: string;
  menuClassName?: string;
};

/**
 * A button with a menu (menu button pattern): opens on click, Enter or arrow keys;
 * arrows move, Escape or Tab closes, focus returns to the button. Clicking outside
 * closes it, so only one menu is open at a time.
 */
export function ActionMenu({ label, items, icon = icons.more, trigger, triggerClassName, menuClassName }: ActionMenuProps) {
  const [open, setOpen] = useState(false);
  const [focusOnOpen, setFocusOnOpen] = useState(0);
  const menuId = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    if (!open) return;
    itemRefs.current[focusOnOpen]?.focus();
    const onDown = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open, focusOnOpen]);

  const close = (returnFocus = true) => {
    setOpen(false);
    if (returnFocus) button.current?.focus();
  };

  const openAt = (index: number) => {
    setFocusOnOpen(index);
    setOpen(true);
  };

  const onButtonKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      openAt(0);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      openAt(items.length - 1);
    }
  };

  const onMenuKey = (e: KeyboardEvent) => {
    const i = itemRefs.current.findIndex((el) => el === document.activeElement);
    const move = (to: number) => {
      e.preventDefault();
      itemRefs.current[(to + items.length) % items.length]?.focus();
    };
    if (e.key === 'ArrowDown') move(i + 1);
    else if (e.key === 'ArrowUp') move(i - 1);
    else if (e.key === 'Home') move(0);
    else if (e.key === 'End') move(items.length - 1);
    else if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'Tab') close(false);
  };

  const buttonProps = {
    'aria-haspopup': 'menu' as const,
    'aria-expanded': open,
    'aria-controls': open ? menuId : undefined,
    onClick: () => (open ? close() : openAt(0)),
    onKeyDown: onButtonKey,
  };

  return (
    <div className="menu-wrap" ref={wrap}>
      {trigger ? (
        <button ref={button} type="button" className={triggerClassName ?? 'menu-trigger'} aria-label={label} {...buttonProps}>
          {trigger}
        </button>
      ) : (
        <IconButton ref={button} label={label} icon={icon} {...buttonProps} />
      )}
      {open ? (
        <div className={menuClassName ? `menu ${menuClassName}` : 'menu'} role="menu" id={menuId} aria-label={label} onKeyDown={onMenuKey}>
          {items.map((item, i) => {
            const className = ['menu-item', item.danger ? 'menu-item-danger' : '', item.current ? 'menu-item-current' : '']
              .filter(Boolean)
              .join(' ');
            const content = (
              <>
                {item.media ?? (item.icon ? <Icon path={item.icon} size={16} /> : null)}
                <span>{item.label}</span>
              </>
            );
            const ref = (el: HTMLElement | null) => {
              itemRefs.current[i] = el;
            };
            return (
              <Fragment key={item.label}>
                {item.heading ? (
                  <div className="menu-heading" role="presentation">
                    {item.heading}
                  </div>
                ) : null}
                {item.href ? (
                  <a
                    ref={ref}
                    href={item.href}
                    role="menuitem"
                    tabIndex={-1}
                    className={className}
                    aria-current={item.current ? 'true' : undefined}
                    onClick={() => close(false)}
                  >
                    {content}
                  </a>
                ) : (
                  <button
                    ref={ref}
                    type="button"
                    role="menuitem"
                    tabIndex={-1}
                    className={className}
                    aria-current={item.current ? 'true' : undefined}
                    onClick={() => {
                      close();
                      item.onSelect?.();
                    }}
                  >
                    {content}
                  </button>
                )}
              </Fragment>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
