import { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { ButtonLink, CountBadge, SearchInput, icons } from '../components/ui';
import { footerNav, mainNav, type NavItem } from './nav';

type Props = {
  /** Number badges by route, e.g. { '/contact-requests': 3 }. */
  badges?: Partial<Record<string, number>>;
  /** Drawer state on narrow screens. Ignored on wide screens. */
  open?: boolean;
};

function Item({ item, badge }: { item: NavItem; badge?: number }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
    >
      <Icon path={item.icon} size={16} />
      {item.label}
      {badge ? <CountBadge count={badge} label={`${badge} new`} /> : null}
    </NavLink>
  );
}

/** "Search..." opens the Surveys list filtered by the typed text (any status). */
function SurveySearch() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const current = pathname === '/surveys' ? (params.get('q') ?? '') : '';
  const [text, setText] = useState(current);

  // Follow the list: "Clear search" there empties this box too.
  useEffect(() => setText(current), [current]);

  return (
    <SearchInput
      label="Search surveys"
      value={text}
      onChange={setText}
      onSearch={(value) => {
        const q = value.trim();
        navigate(q ? `/surveys?${new URLSearchParams({ q })}` : '/surveys');
      }}
    />
  );
}

export function Sidebar({ badges = {}, open = false }: Props) {
  return (
    <nav id="sideNav" className={open ? 'sidebar open' : 'sidebar'} aria-label="Sidebar">
      <ButtonLink to="/surveys/new" variant="primary" icon={icons.plus} block>
        Create survey
      </ButtonLink>
      <SurveySearch />
      {mainNav.map((item) => (
        <Item key={item.to} item={item} badge={badges[item.to]} />
      ))}
      <div className="sidebar-divider" role="separator" />
      <div className="sidebar-footer">
        {footerNav.map((item) => (
          <Item key={item.to} item={item} />
        ))}
      </div>
    </nav>
  );
}
