import { PageHeader } from './PageHeader';
import { Card } from './ui';

type Props = { title: string; description: string; card: string };

/** Empty page shown until the backlog card for this page is built. */
export function PlaceholderPage({ title, description, card }: Props) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <Card padded>
        <p style={{ margin: 0 }}>
          Not built yet. Backlog card: <strong>{card}</strong>
        </p>
      </Card>
    </>
  );
}
