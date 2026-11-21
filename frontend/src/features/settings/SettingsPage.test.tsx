import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ToastProvider } from '../../components/ui';
import { readFlag, writeFlag } from './featureFlags';
import { SettingsPage } from './SettingsPage';

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

function renderPage() {
  render(
    <MemoryRouter>
      <ToastProvider>
        <SettingsPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

const newsSwitch = () => screen.getByRole('switch', { name: 'News and inspiration' });

test('Settings has a Feature flags section with News and inspiration off by default', () => {
  renderPage();
  expect(screen.getByRole('heading', { name: 'Feature flags' })).toBeInTheDocument();
  expect(newsSwitch()).toHaveAttribute('aria-checked', 'false');
  expect(newsSwitch()).toHaveAccessibleDescription('Show the Recent news and Get inspired articles on the front page.');
});

test('the switch saves the choice in this browser', () => {
  renderPage();
  fireEvent.click(newsSwitch());
  expect(newsSwitch()).toHaveAttribute('aria-checked', 'true');
  expect(localStorage.getItem('lianasurvey.flag.newsAndInspiration')).toBe('true');
  expect(readFlag('newsAndInspiration')).toBe(true);
  fireEvent.click(newsSwitch());
  expect(newsSwitch()).toHaveAttribute('aria-checked', 'false');
  expect(readFlag('newsAndInspiration')).toBe(false);
});

test('a saved choice is shown, and a change in another tab is picked up', () => {
  writeFlag('newsAndInspiration', true);
  renderPage();
  expect(newsSwitch()).toHaveAttribute('aria-checked', 'true');
  localStorage.setItem('lianasurvey.flag.newsAndInspiration', 'false');
  act(() => {
    window.dispatchEvent(new StorageEvent('storage', { key: 'lianasurvey.flag.newsAndInspiration' }));
  });
  expect(newsSwitch()).toHaveAttribute('aria-checked', 'false');
});

test('odd stored values fall back to the default', () => {
  localStorage.setItem('lianasurvey.flag.newsAndInspiration', 'yes');
  expect(readFlag('newsAndInspiration')).toBe(false);
});

test('when the browser blocks storage the switch still works until reload, and says so', async () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('blocked', 'QuotaExceededError');
  });
  renderPage();
  fireEvent.click(newsSwitch());
  expect(newsSwitch()).toHaveAttribute('aria-checked', 'true');
  expect(await screen.findByText(/did not let us save this/)).toBeInTheDocument();
});
