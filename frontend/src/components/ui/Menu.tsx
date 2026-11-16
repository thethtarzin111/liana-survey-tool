import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Icon } from '../Icon';
import { IconButton } from './Button';
import { icons } from './icons';

export type MenuAction = {
  label: string;
  onSelect: () => void;
  icon?: string;
  /** Red text, for Delete and similar. */
  danger?: boolean;
};

type ActionMenuProps = {
  /** Name of the ⋯ button, e.g. "Actions for Member NPS 2026". */
  label: string;
  items: MenuAction[];
  /** Custom trigger icon; defaults to ⋯. */
  icon?: string;
};

/**
 * ⋯ button with a menu of actions (menu button pattern): opens on click,
 * Enter or arrow keys; arrows move, Escape or Tab closes, focus returns to the button.
 */
export function ActionMenu({ label, items, icon = icons.more }: ActionMenuProps) {
  const [open, setOpen] = useState(false);
  const [focusOnOpen, setFocusOnOpen] = useState(0);
  const menuId = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

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

  return (
    <div className="menu-wrap" ref={wrap}>
      <IconButton
        ref={button}
        label={label}
        icon={icon}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => (open ? close() : openAt(0))}
        onKeyDown={onButtonKey}
      />
      {open ? (
        <div className="menu" role="menu" id={menuId} aria-label={label} onKeyDown={onMenuKey}>
          {items.map((item, i) => (
            <button
              key={item.label}
              ref={(el) => {
                itemRefs.current[i] = el;
              }}
              type="button"
              role="menuitem"
              tabIndex={-1}
              className={item.danger ? 'menu-item menu-item-danger' : 'menu-item'}
              onClick={() => {
                close();
                item.onSelect();
              }}
            >
              {item.icon ? <Icon path={item.icon} size={16} /> : null}
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
