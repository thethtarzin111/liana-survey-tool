import { useCurrentUser } from '../../api/useCurrentUser';
import { PerformancePanel } from './PerformancePanel';
import { PageHeader } from '../../components/PageHeader';
import { ButtonLink, Card, icons } from '../../components/ui';

export function FrontPage() {
  const user = useCurrentUser();
  return (
    <>
      <PageHeader
        title={user ? `Welcome, ${user.name.split(' ')[0]}` : 'Welcome'}
        description="Your surveys and the latest results at a glance."
        actions={
          <ButtonLink to="/surveys/new" variant="primary" icon={icons.plus}>
            Create survey
          </ButtonLink>
        }
      />
      <Card padded>
        <p style={{ margin: 0 }}>
          Not built yet. Backlog cards: <strong>Front page banner</strong>,{' '}
          <strong>Overview tiles</strong>, <strong>Your surveys</strong>,{' '}
          <strong>Survey performance table</strong>.
        </p>
      </Card>
      <PerformancePanel />
    </>
  );
}
