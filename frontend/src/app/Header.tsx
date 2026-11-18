import type { RefObject } from 'react';
import { useCurrentUser } from '../api/useCurrentUser';
import { Icon } from '../components/Icon';

type Props = {
  navOpen: boolean;
  onToggleNav: () => void;
  menuButtonRef?: RefObject<HTMLButtonElement>;
};

export function Header({ navOpen, onToggleNav, menuButtonRef }: Props) {
  const user = useCurrentUser();
  return (
    <header className="header">
      {/* Only shown on narrow screens, where the sidebar becomes a drawer. */}
      <button
        ref={menuButtonRef}
        type="button"
        className="icon-button header-menu"
        aria-label="Menu"
        aria-expanded={navOpen}
        aria-controls="sideNav"
        onClick={onToggleNav}
      >
        <Icon path="M4 7h16M4 12h16M4 17h16" size={22} />
      </button>
      <span className="header-brand"><Icon path="M5 3h14v18H5zM8 7h8M8 11h8M8 15h5" size={24} /><span className="brand-liana">Liana</span><span className="brand-survey">survey</span></span>
      <span className="header-spacer" />
      {/* TODO card "Apps switcher": LianaSurvey / LianaMailer / LianaAutomation */}
      <span className="header-user">{user ? <><span className="header-avatar" aria-hidden="true">{user.name.split(' ').map(part => part[0]).slice(0,2).join('')}</span><span><strong>{user.name}</strong><small>{user.tenant_name}</small></span></> : null}</span>
    </header>
  );
}
