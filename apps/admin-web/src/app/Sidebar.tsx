import { Link, NavLink } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { footerNav, mainNav, type NavItem } from './nav';

type Props = {
  /** Number badges by route, e.g. { '/contact-requests': 3 }. */
  badges?: Partial<Record<string, number>>;
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
      {badge ? (
        <span className="badge" aria-label={`${badge} new`}>
          {badge}
        </span>
      ) : null}
    </NavLink>
  );
}

export function Sidebar({ badges = {} }: Props) {
  return (
    <nav className="sidebar" aria-label="Sidebar">
      <Link to="/surveys/new" className="btn btn-primary">
        <Icon path="M12 5v14M5 12h14" size={16} strokeWidth={2.4} />
        Create survey
      </Link>
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
