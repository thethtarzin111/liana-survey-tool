import { render, screen } from '@testing-library/react';
import { ResultsPage } from './ResultsPage';

afterEach(() => vi.unstubAllGlobals());

test('shows performance by survey and channel', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json([{ survey_id:'s1',survey:'Member NPS',channel:'email',views:120,responses:30,response_rate:25,main_result:'NPS +42' }])));
  render(<ResultsPage />);
  expect(await screen.findByRole('table', { name: 'Survey performance' })).toBeInTheDocument();
  expect(screen.getByText('Email')).toBeInTheDocument();
  expect(screen.getByText('25%')).toBeInTheDocument();
  expect(screen.getByText('NPS +42')).toBeInTheDocument();
});

test('shows an empty state before a survey has views', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json([])));
  render(<ResultsPage />);
  expect(await screen.findByText('No performance data yet.')).toBeInTheDocument();
});
