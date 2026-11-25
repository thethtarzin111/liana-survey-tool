import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { WelcomeBanner } from './WelcomeBanner';

const HEADING = 'Welcome to LianaSurvey – hear what your readers think';

function renderBanner() {
  return render(
    <MemoryRouter>
      <WelcomeBanner />
    </MemoryRouter>,
  );
}
afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

test('a first visit shows the open banner with both ways to start', () => {
  renderBanner();
  const banner = screen.getByRole('region', { name: HEADING });
  expect(within(banner).getByRole('heading', { level: 1, name: HEADING })).toBeInTheDocument();
  expect(within(banner).getByRole('link', { name: 'Create survey' })).toHaveAttribute('href', '/surveys/new');
  expect(within(banner).getByRole('link', { name: 'Browse templates' })).toHaveAttribute('href', '/templates');
  const toggle = within(banner).getByRole('button', { name: 'Fold up the welcome banner' });
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  expect(toggle).toHaveAttribute('aria-controls', 'welcome-body');
  // The newsletter picture is decoration only.
  expect(within(banner).queryByText('84% positive')?.closest('[aria-hidden="true"]')).not.toBeNull();
});

test('folding hides the banner content and the toggle opens it again', () => {
  renderBanner();
  fireEvent.click(screen.getByRole('button', { name: 'Fold up the welcome banner' }));

  const toggle = screen.getByRole('button', { name: 'Show the welcome banner' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(screen.getAllByRole('button')).toHaveLength(1);

  fireEvent.click(toggle);
  expect(screen.getByRole('button', { name: 'Fold up the welcome banner' })).toHaveAttribute('aria-expanded', 'true');
});

test('the banner stays folded on the next visit', () => {
  const first = renderBanner();
  fireEvent.click(screen.getByRole('button', { name: 'Fold up the welcome banner' }));
  first.unmount();

  renderBanner();
  expect(screen.getByRole('button', { name: 'Show the welcome banner' })).toHaveAttribute('aria-expanded', 'false');
});

test('blocked storage opens the banner and still lets it fold', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new DOMException('blocked', 'SecurityError');
  });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('blocked', 'SecurityError');
  });
  renderBanner();

  fireEvent.click(screen.getByRole('button', { name: 'Fold up the welcome banner' }));
  expect(screen.getByRole('button', { name: 'Show the welcome banner' })).toHaveAttribute('aria-expanded', 'false');
});
