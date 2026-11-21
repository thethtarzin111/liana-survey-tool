import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ToastProvider } from '../components/ui';
import { initials } from '../components/ui/Avatar';
import { lianaApps } from '../config/lianaApps';
import { Header } from './Header';

const STAGING = lianaApps({
  VITE_LIANA_MAILER_URL: 'https://testing.lianamailer.com/v/welcome',
  VITE_LIANA_MONITOR_URL: 'https://staging.lianamonitor.com/home',
  VITE_LIANA_AUTOMATION_URL: ' ',
  VITE_LIANA_ACCOUNT_URL: undefined,
});

beforeEach(() => {
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

function renderHeader() {
  render(
    <MemoryRouter>
      <ToastProvider>
        <Header navOpen={false} onToggleNav={() => {}} apps={STAGING} />
      </ToastProvider>
    </MemoryRouter>,
  );
}

const appsButton = () => screen.getByRole('button', { name: 'Liana apps' });
const userButton = () => screen.getByRole('button', { name: 'Account: Anna Virtanen' });

test('the logo goes to the front page', () => {
  renderHeader();
  expect(screen.getByRole('link', { name: 'LianaSurvey home' })).toHaveAttribute('href', '/');
});

test('Support chat and Help say they are not available yet', async () => {
  renderHeader();
  fireEvent.click(screen.getByRole('button', { name: 'Support chat' }));
  expect(await screen.findByText('Support chat is not available yet.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Help' }));
  expect(await screen.findByText('Help is not available yet.')).toBeInTheDocument();
});

test('the apps menu lists the Liana apps with links from the settings', async () => {
  renderHeader();
  await screen.findByRole('button', { name: 'Account: Anna Virtanen' });
  fireEvent.click(appsButton());
  const menu = screen.getByRole('menu', { name: 'Liana apps' });
  const items = within(menu).getAllByRole('menuitem');
  expect(items.map((item) => item.textContent)).toEqual([
    'LianaSurvey - Example Members Association',
    'LianaMailer - Example Members Association',
    'LianaMonitor - Example Members Association',
    'LianaAutomation',
    'LianaAccount',
  ]);
  expect(menu).toHaveTextContent('Others');
  expect(items[0]).toHaveAttribute('aria-current', 'true');
  expect(items[0]).toHaveFocus();
  expect(items[1]).toHaveAttribute('href', 'https://testing.lianamailer.com/v/welcome');
  expect(items[2]).toHaveAttribute('href', 'https://staging.lianamonitor.com/home');
  // Apps without an address (blank or not set) are buttons that say so.
  expect(items[3]).not.toHaveAttribute('href');
  fireEvent.click(items[4]);
  expect(await screen.findByText('LianaAccount is not available yet.')).toBeInTheDocument();
});

test('the user menu shows the initials, name and organisation, with placeholder items', async () => {
  renderHeader();
  const button = await screen.findByRole('button', { name: 'Account: Anna Virtanen' });
  expect(button).toHaveTextContent('AV');
  expect(button).toHaveTextContent('Example Members Association');
  fireEvent.click(button);
  const items = within(screen.getByRole('menu', { name: 'Account: Anna Virtanen' })).getAllByRole('menuitem');
  expect(items.map((item) => item.textContent)).toEqual(['User account', 'Organization account', 'Sign out']);
  fireEvent.click(items[2]);
  expect(await screen.findByText('Sign out is not available yet.')).toBeInTheDocument();
  expect(screen.queryByRole('menu')).not.toBeInTheDocument();
});

test('Escape closes a menu and focus returns to its button; one menu at a time', async () => {
  renderHeader();
  await screen.findByRole('button', { name: 'Account: Anna Virtanen' });
  fireEvent.click(appsButton());
  fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape' });
  expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  expect(appsButton()).toHaveFocus();

  fireEvent.keyDown(appsButton(), { key: 'ArrowDown' });
  expect(screen.getByRole('menu', { name: 'Liana apps' })).toBeInTheDocument();
  // Opening the user menu closes the apps menu.
  fireEvent.mouseDown(userButton());
  fireEvent.click(userButton());
  expect(screen.getAllByRole('menu')).toHaveLength(1);
  expect(screen.getByRole('menu', { name: 'Account: Anna Virtanen' })).toBeInTheDocument();
  expect(appsButton()).toHaveAttribute('aria-expanded', 'false');
});

test('initials are the first letters of the first two names', () => {
  expect(initials('Anna Virtanen')).toBe('AV');
  expect(initials('  maria  de la cruz ')).toBe('MD');
  expect(initials('Cher')).toBe('C');
  expect(initials('')).toBe('');
});
