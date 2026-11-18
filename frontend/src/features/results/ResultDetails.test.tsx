import { render, screen } from '@testing-library/react';
import { ResultDetails } from './ResultDetails';

afterEach(() => vi.unstubAllGlobals());

test.each(['reasons', 'comments'] as const)('%s displays an empty state for the selected segment', async (view) => {
  const fetchMock = vi.fn(async () => Response.json([]));
  vi.stubGlobal('fetch', fetchMock);
  render(<ResultDetails surveyId="survey" segment="members" view={view} />);
  expect(await screen.findByText(view === 'reasons' ? 'No reasons yet.' : 'No comments yet.')).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(`/api/v1/results/survey/${view}?segment=members`, expect.anything());
});
