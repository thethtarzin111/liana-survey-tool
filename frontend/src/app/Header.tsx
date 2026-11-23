import { useEffect, useState, type RefObject } from 'react';
import { Link } from 'react-router-dom';
import { api, type DemoOrganization } from '../api/client';
import { useCurrentUser } from '../api/useCurrentUser';
import { Icon } from '../components/Icon';
import { LianaSurveyLogo } from '../components/LianaSurveyLogo';
import { ActionMenu, Avatar, useToast, type MenuAction } from '../components/ui';
import { lianaApps, type LianaApp } from '../config/lianaApps';

type Props = {
  navOpen: boolean;
  onToggleNav: () => void;
  menuButtonRef?: RefObject<HTMLButtonElement>;
  /** The other Liana apps; by default from this build's settings. */
  apps?: LianaApp[];
  /** After switching organisation: reload the app, so nothing of the old one stays on screen. */
  onSwitched?: () => void;
};

const ICONS = {
  chat: 'M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z',
  help: 'M9 9a3 3 0 1 1 4 2.8c-.6.3-1 .9-1 1.6V15M12 19h.01',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 20c.8-3.5 3.6-5.5 7-5.5s6.2 2 7 5.5',
  organization: 'M6 3h12v18H6zM10 21v-3h4v3M9.5 7h1M13.5 7h1M9.5 10.5h1M13.5 10.5h1M9.5 14h1M13.5 14h1',
  signOut: 'M10 4H5v16h5M14 8l4 4-4 4M18 12H9',
  chevron: 'M6 9l6 6 6-6',
};

function AppsIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      {[3, 10, 17].flatMap((y) => [3, 10, 17].map((x) => <rect key={`${x}-${y}`} x={x} y={y} width="4" height="4" rx="1" />))}
    </svg>
  );
}

function AppIcon({ color, icon }: { color: string; icon: string }) {
  return (
    <span className="app-icon" style={{ background: color }} aria-hidden="true">
      <Icon path={icon} size={18} />
    </span>
  );
}

/** The top bar, as in the other Liana apps (#74). */
export function Header({
  navOpen, onToggleNav, menuButtonRef, apps: liana = lianaApps(), onSwitched = () => window.location.assign('/'),
}: Props) {
  const user = useCurrentUser();
  const toast = useToast();
  const [organizations, setOrganizations] = useState<DemoOrganization[]>([]);

  useEffect(() => {
    let alive = true;
    // Only the dev-auth gateway lists demo organisations. Without the list, there is no switcher.
    api.demoOrganizations().then(
      (list) => { if (alive && Array.isArray(list)) setOrganizations(list); },
      () => {},
    );
    return () => { alive = false; };
  }, []);

  async function switchTo(organization: DemoOrganization) {
    if (organization.current) return;
    try {
      await api.switchOrganization(organization.tenant_id);
      onSwitched();
    } catch {
      toast('We couldn’t switch the organization. Please try again.');
    }
  }
  const notYet = (what: string) => () => toast(`${what} is not available yet.`);
  const org = user?.tenant_name;
  const withOrg = (name: string) => (org ? `${name} - ${org}` : name);

  const appItem = (app: LianaApp, heading?: string): MenuAction => ({
    label: app.other ? app.name : withOrg(app.name),
    media: <AppIcon color={app.color} icon={app.icon} />,
    heading,
    ...(app.url ? { href: app.url } : { onSelect: notYet(app.name) }),
  });
  const others = liana.filter((app) => app.other);
  // LianaSurvey itself is left out: you are already in it.
  const apps: MenuAction[] = [
    ...liana.filter((app) => !app.other).map((app) => appItem(app)),
    ...others.map((app, i) => appItem(app, i === 0 ? 'Others' : undefined)),
  ];

  // Login is out of scope (dev-auth stub), so these are placeholders.
  const account: MenuAction[] = [
    { label: 'User account', icon: ICONS.user, onSelect: notYet('User account') },
    { label: 'Organization account', icon: ICONS.organization, onSelect: notYet('Organization account') },
    { label: 'Sign out', icon: ICONS.signOut, onSelect: notYet('Sign out') },
    // The demo has no real login: switching shows that organisations are kept apart.
    ...(organizations.length > 1
      ? organizations.map((organization, i): MenuAction => ({
        label: organization.tenant_name,
        icon: ICONS.organization,
        current: organization.current,
        heading: i === 0 ? 'Switch organization (demo)' : undefined,
        onSelect: () => { void switchTo(organization); },
      }))
      : []),
  ];

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
      <Link to="/" className="header-logo" aria-label="LianaSurvey home">
        <LianaSurveyLogo />
      </Link>
      <div className="header-actions">
        <button type="button" className="header-pill" aria-label="Support chat" onClick={notYet('Support chat')}>
          <Icon path={ICONS.chat} size={16} />
          <span className="header-wide">Support chat</span>
        </button>
        <button type="button" className="header-icon" aria-label="Help" onClick={notYet('Help')}>
          <Icon path={ICONS.help} size={20} />
        </button>
        <ActionMenu
          label="Liana apps"
          items={apps}
          trigger={<AppsIcon />}
          triggerClassName="header-icon"
          menuClassName="header-apps"
        />
        {user?.name ? (
          <ActionMenu
            label={`Account: ${user.name}`}
            items={account}
            trigger={
              <>
                <Avatar name={user.name} />
                <span className="header-who header-wide">
                  <strong>{user.name}</strong>
                  <span>{user.tenant_name}</span>
                </span>
                <span className="header-chevron header-wide">
                  <Icon path={ICONS.chevron} size={16} />
                </span>
              </>
            }
            triggerClassName="header-user"
            menuClassName="header-account"
          />
        ) : null}
      </div>
    </header>
  );
}
