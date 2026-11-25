import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ToastProvider } from '../../components/ui';
import { LoginPage, nextPath } from './LoginPage';

type Handler = (body: { email: string; password: string }) => Response;

/** /me answers 401 (signed out); the login request gets the handler's response. */
function stubApi(login: Handler = () => Response.json({ name: 'Anna Virtanen' })) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/v1/auth/login') return login(JSON.parse(String(init?.body)));
    return Response.json({ detail: 'Sign in with a demo login' }, { status: 401 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

let assign: ReturnType<typeof vi.fn>;
beforeEach(() => {
  assign = vi.fn();
  vi.stubGlobal('location', { ...window.location, assign });
});
afterEach(() => vi.unstubAllGlobals());

function renderLogin(url = '/login') {
  render(
    <MemoryRouter initialEntries={[url]}>
      <ToastProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<p>The app</p>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

const emailField = () => screen.getByLabelText('Email address*');
const passwordField = () => screen.getByLabelText('Password');
const continueButton = () => screen.getByRole('button', { name: 'Continue' });

function enterEmail(email = 'anna.virtanen@example.org') {
  fireEvent.change(emailField(), { target: { value: email } });
  fireEvent.click(continueButton());
}

test('signs in with the email address, then the password, and goes back to the page asked for', async () => {
  const fetchMock = stubApi();
  renderLogin('/login?next=%2Fresults%3Ftab%3Dresponses');
  expect(screen.getByRole('heading', { name: 'Welcome' })).toBeInTheDocument();
  enterEmail(' anna.virtanen@example.org ');

  expect(screen.getByRole('heading', { name: 'Enter Your Password' })).toBeInTheDocument();
  expect(screen.getByText('anna.virtanen@example.org')).toBeInTheDocument();
  fireEvent.change(passwordField(), { target: { value: 'secret' } });
  fireEvent.click(continueButton());

  await vi.waitFor(() => expect(assign).toHaveBeenCalledWith('/results?tab=responses'));
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/v1/auth/login',
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ email: 'anna.virtanen@example.org', password: 'secret' }) }),
  );
});

test('a wrong email address or password shows an error and stays on the password step', async () => {
  stubApi(() => Response.json({ detail: 'Wrong email address or password' }, { status: 401 }));
  renderLogin();
  enterEmail();
  fireEvent.change(passwordField(), { target: { value: 'wrong' } });
  fireEvent.click(continueButton());
  expect(await screen.findByRole('alert')).toHaveTextContent('Wrong email address or password.');
  expect(passwordField()).toHaveAttribute('aria-invalid', 'true');
  expect(assign).not.toHaveBeenCalled();
});

test('an empty email address or password is asked for', () => {
  stubApi();
  renderLogin();
  fireEvent.click(continueButton());
  expect(screen.getByRole('alert')).toHaveTextContent('Enter your email address.');
  enterEmail();
  fireEvent.click(continueButton());
  expect(screen.getByRole('alert')).toHaveTextContent('Enter your password.');
});

test('Edit goes back to the email step with the address kept', () => {
  stubApi();
  renderLogin();
  enterEmail();
  fireEvent.click(screen.getByRole('button', { name: 'Edit email address' }));
  expect(emailField()).toHaveValue('anna.virtanen@example.org');
});

test('the password can be shown and hidden', () => {
  stubApi();
  renderLogin();
  enterEmail();
  expect(passwordField()).toHaveAttribute('type', 'password');
  fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
  expect(passwordField()).toHaveAttribute('type', 'text');
  fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
  expect(passwordField()).toHaveAttribute('type', 'password');
});

test('single sign-on, Reset password and Privacy Policy say they are not in the demo', async () => {
  stubApi();
  renderLogin();
  fireEvent.click(screen.getByRole('button', { name: 'Continue: Liana Technologies' }));
  expect(await screen.findByText('Signing in with Liana Technologies is not in the demo.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Privacy Policy' }));
  expect(await screen.findByText('The privacy policy is not in the demo.')).toBeInTheDocument();
  enterEmail();
  fireEvent.click(screen.getByRole('button', { name: 'Reset password' }));
  expect(await screen.findByText('Resetting the password is not in the demo.')).toBeInTheDocument();
});

test('when already signed in (always, locally) it goes straight to the app', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ name: 'Anna Virtanen' })));
  renderLogin();
  expect(await screen.findByText('The app')).toBeInTheDocument();
});

test('after signing in it only goes to pages of this app', () => {
  expect(nextPath('?next=%2Fsurveys')).toBe('/surveys');
  expect(nextPath('?next=https%3A%2F%2Fevil.example')).toBe('/');
  expect(nextPath('?next=%2F%2Fevil.example')).toBe('/');
  expect(nextPath('?next=%2Flogin')).toBe('/');
  expect(nextPath('')).toBe('/');
});
