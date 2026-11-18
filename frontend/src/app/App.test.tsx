import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ToastProvider } from '../components/ui';
import { App } from './App';
import { Sidebar } from './Sidebar';

beforeEach(() => {
  // No API in unit tests: pretend the dev-auth stub answered.
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      Response.json({
        user_id: 'u',
        tenant_id: 't',
        tenant_name: 'Example Members Association',
        name: 'Anna Virtanen',
        email: 'anna.virtanen@example.org',
      }),
    ),
  );
});

afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      {/* As in main.tsx. */}
      <ToastProvider>
        <App />
      </ToastProvider>
    </MemoryRouter>,
  );
}

test('sidebar has the prototype items in order', () => {
  render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
  const labels = screen.getAllByRole('link').map((a) => a.textContent);
  expect(labels).toEqual([
    'Create survey',
    'Home',
    'Surveys',
    'Templates',
    'Results',
    'Contact requests',
    'Integrations',
    'Support',
    'Settings',
  ]);
});

test('front page shows the dashboard', async () => {
  renderAt('/');
  expect(await screen.findByRole('heading', { name: 'Get started with LianaSurvey' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page');
});

test('a sidebar route renders its page', () => {
  renderAt('/contact-requests');
  expect(screen.getByRole('heading', { name: 'Contact requests' })).toBeInTheDocument();
});

test('/responses lands on Results with the Responses tab', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.startsWith('/api/v1/surveys')) {
        return Response.json([
          { id: 's1', title: 'Member NPS', type: 'nps', status: 'live', answers: 3, last_answer_at: null, headline: null },
        ]);
      }
      if (path.includes('/responses')) return Response.json({ total: 0, rows: [] });
      return Response.json({
        survey_id: 's1', title: 'Member NPS', type: 'nps', status: 'live', closes_at: null, last_answer_at: null,
        channels: [], segment: 'all', segments: [], responses: 3, views: 0, response_rate: null, completed_all: null,
        main: null, questions: [], reasons: [], trend: [], by_segment: [],
      });
    }),
  );
  renderAt('/responses');
  expect(await screen.findByRole('tab', { name: 'Responses 3' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('heading', { name: 'Results' })).toBeInTheDocument();
});

test('sidebar shows a badge when given a count', () => {
  render(
    <MemoryRouter>
      <Sidebar badges={{ '/contact-requests': 3 }} />
    </MemoryRouter>,
  );
  expect(screen.getByLabelText('3 new')).toBeInTheDocument();
});

test('menu button opens the sidebar drawer; navigating or Escape closes it', () => {
  renderAt('/');
  const menu = screen.getByRole('button', { name: 'Menu' });
  const nav = screen.getByRole('navigation', { name: 'Sidebar' });
  expect(menu).toHaveAttribute('aria-expanded', 'false');

  fireEvent.click(menu);
  expect(menu).toHaveAttribute('aria-expanded', 'true');
  expect(nav).toHaveClass('open');

  fireEvent.click(screen.getByRole('link', { name: 'Templates' }));
  expect(nav).not.toHaveClass('open');

  fireEvent.click(menu);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(nav).not.toHaveClass('open');
  expect(menu).toHaveFocus();
});
