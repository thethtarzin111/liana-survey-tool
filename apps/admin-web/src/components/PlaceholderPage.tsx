import { PageHeader } from './PageHeader';

type Props = { title: string; description: string; card: string };

/** Empty page shown until the backlog card for this page is built. */
export function PlaceholderPage({ title, description, card }: Props) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <section className="card">
        <p style={{ margin: 0 }}>
          Not built yet. Backlog card: <strong>{card}</strong>
        </p>
      </section>
    </>
  );
}
