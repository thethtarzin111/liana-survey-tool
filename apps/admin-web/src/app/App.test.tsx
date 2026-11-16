import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
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
      <App />
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
    'Results',
    'Responses',
    'Contact requests',
    'Templates',
    'Integrations',
    'Support',
    'Settings',
  ]);
});

test('front page greets the demo user', async () => {
  renderAt('/');
  expect(await screen.findByRole('heading', { name: 'Welcome, Anna' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page');
});

test('a sidebar route renders its page', () => {
  renderAt('/contact-requests');
  expect(screen.getByRole('heading', { name: 'Contact requests' })).toBeInTheDocument();
});

test('sidebar shows a badge when given a count', () => {
  render(
    <MemoryRouter>
      <Sidebar badges={{ '/contact-requests': 3 }} />
    </MemoryRouter>,
  );
  expect(screen.getByLabelText('3 new')).toBeInTheDocument();
});
