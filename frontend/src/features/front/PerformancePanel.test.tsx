import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { PerformanceRow } from '../../api/client';
import { PerformancePanel } from './PerformancePanel';

const emailRow: PerformanceRow = {
  survey_id: 's1',
  survey: 'Member NPS',
  channel: 'email',
  views: 120,
  responses: 30,
  response_rate: 25,
  main_result: 'NPS +42',
};

function stubRows(...answers: Array<PerformanceRow[] | 'fail'>) {
  const fetchMock = vi.fn<typeof fetch>(async () => {
    const next = answers.length > 1 ? answers.shift()! : answers[0];
    return next === 'fail' ? new Response('down', { status: 500 }) : Response.json(next);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function renderPanel() {
  return render(
    <MemoryRouter>
      <PerformancePanel />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test('lists each survey and channel with its rate and main result', async () => {
  stubRows([emailRow, { ...emailRow, channel: 'qr', views: 0, responses: 0, response_rate: null, main_result: null }]);
  renderPanel();
  const table = await screen.findByRole('table', { name: 'Survey performance' });
  const [email, qr] = within(table).getAllByRole('row').slice(1);
  expect(email).toHaveTextContent('Member NPS');
  expect(email).toHaveTextContent('Email');
  expect(email).toHaveTextContent('25%');
  expect(email).toHaveTextContent('NPS +42');
  expect(qr).toHaveTextContent('QR code');
  expect(within(qr).getAllByText('—')).toHaveLength(2);
});

test('says there is nothing to report before any survey is viewed', async () => {
  stubRows([]);
  renderPanel();
  expect(await screen.findByText('Nothing to report yet')).toBeInTheDocument();
});

test('a failed load can be tried again', async () => {
  stubRows('fail', [emailRow]);
  renderPanel();
  expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t load survey performance.');
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByRole('table', { name: 'Survey performance' })).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('refreshes while the page is open, so new answers show up', async () => {
  vi.useFakeTimers();
  const fetchMock = stubRows([], [emailRow]);
  renderPanel();
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(screen.getByText('Nothing to report yet')).toBeInTheDocument();

  await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(screen.getByRole('table', { name: 'Survey performance' })).toBeInTheDocument();
});

test('asks for the 5 surveys with the latest activity and links to the full report', async () => {
  const fetchMock = stubRows([emailRow]);
  renderPanel();
  await screen.findByRole('table', { name: 'Survey performance' });
  expect(String(fetchMock.mock.calls[0][0])).toBe('/api/v1/results/performance?limit=5');
  expect(screen.getByRole('link', { name: 'View all →' })).toHaveAttribute('href', '/surveys');
});
