import { Link } from 'react-router-dom';
import { useCurrentUser } from '../../api/useCurrentUser';
import { PageHeader } from '../../components/PageHeader';

export function FrontPage() {
  const user = useCurrentUser();
  return (
    <>
      <PageHeader
        title={user ? `Welcome, ${user.name.split(' ')[0]}` : 'Welcome'}
        description="Your surveys and the latest results at a glance."
        actions={
          <Link to="/surveys/new" className="btn btn-primary">
            + Create survey
          </Link>
        }
      />
      <section className="card">
        <p style={{ margin: 0 }}>
          Not built yet. Backlog cards: <strong>Front page banner</strong>,{' '}
          <strong>Overview tiles</strong>, <strong>Your surveys</strong>,{' '}
          <strong>Survey performance table</strong>.
        </p>
      </section>
    </>
  );
}
