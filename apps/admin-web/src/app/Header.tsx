import { useCurrentUser } from '../api/useCurrentUser';

export function Header() {
  const user = useCurrentUser();
  return (
    <header className="header">
      <span className="header-brand">LianaSurvey</span>
      <span className="header-spacer" />
      {/* TODO card "Apps switcher": LianaSurvey / LianaMailer / LianaAutomation */}
      <span className="header-user">{user ? `${user.name} · ${user.tenant_name}` : ''}</span>
    </header>
  );
}
