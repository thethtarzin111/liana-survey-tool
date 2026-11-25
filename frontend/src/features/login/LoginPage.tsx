import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../api/client';
import googleIcon from '../../assets/google-icon.png';
import logo from '../../assets/liana-logo.png';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/ui';
import './login.css';

const EYE = 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z';
const EYE_OFF = 'M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3 3.8M6.6 6.6A17 17 0 0 0 2 12s3.6 7 10 7a10 10 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2';

/** Where to go after signing in: a page of this app, never another site. */
export function nextPath(search: string): string {
  const next = new URLSearchParams(search).get('next') ?? '';
  // Parse it as the browser will: "//x", "/\x" and "https://x" all leave the app.
  const app = 'https://app.invalid';
  let url: URL;
  try {
    url = new URL(next, app);
  } catch {
    return '/';
  }
  if (!next.startsWith('/') || url.origin !== app || url.pathname.startsWith('/login')) return '/';
  return url.pathname + url.search + url.hash;
}

/**
 * The demo server's login page, after the prototype (LianaAccount's two steps:
 * email address, then password). The gateway checks the demo login and sets the
 * session cookie. Locally everyone stays signed in, so this page goes straight on.
 */
export function LoginPage() {
  const { search } = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const [step, setStep] = useState<'email' | 'password'>('email');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const emailInput = useRef<HTMLInputElement>(null);
  const passwordInput = useRef<HTMLInputElement>(null);
  const next = nextPath(search);

  // Already signed in (always, locally): go on to the app.
  useEffect(() => {
    let alive = true;
    api
      .me()
      .then(() => {
        if (alive) navigate(next, { replace: true });
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [navigate, next]);

  useEffect(() => {
    (step === 'email' ? emailInput : passwordInput).current?.focus();
  }, [step]);

  const notInDemo = (what: string) => () => toast(`${what} is not in the demo.`);

  function continueWithEmail(e: FormEvent) {
    e.preventDefault();
    if (!email.trim()) {
      setError('Enter your email address.');
      return;
    }
    setError('');
    setStep('password');
  }

  async function signIn(e: FormEvent) {
    e.preventDefault();
    if (!password) {
      setError('Enter your password.');
      return;
    }
    setBusy(true);
    try {
      await api.login(email.trim(), password);
      // A full load, so every page starts with the new organisation.
      window.location.assign(next);
    } catch (err) {
      setBusy(false);
      setError(
        err instanceof ApiError && err.status === 401
          ? 'Wrong email address or password.'
          : 'We couldn’t sign you in. Please try again.',
      );
    }
  }

  function editEmail() {
    setError('');
    setPassword('');
    setShowPassword(false);
    setStep('email');
  }

  return (
    <div className="login">
      <svg className="login-curve" aria-hidden="true" viewBox="0 0 2000 900" preserveAspectRatio="none">
        <path d="M0 470C180 450 300 640 560 640C820 640 1000 520 1180 380C1420 190 1700 60 2000 0V-10H0Z" />
      </svg>
      <img className="login-logo" src={logo} alt="Liana" width={210} height={62} />
      <main className="login-card">
        {step === 'email' ? (
          <form className="login-form" onSubmit={continueWithEmail} noValidate>
            <div className="login-heading">
              <h1>Welcome</h1>
              <p>Sign in to LianaSurvey Web</p>
            </div>
            <div className="login-float">
              <input
                ref={emailInput}
                id="login-email"
                className="login-input"
                type="email"
                autoComplete="username"
                placeholder=" "
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? 'login-error' : undefined}
              />
              <label htmlFor="login-email">Email address*</label>
            </div>
            {error ? <p id="login-error" className="login-error" role="alert">{error}</p> : null}
            <button type="submit" className="login-button">Continue</button>
            <div className="login-or">OR</div>
            <button type="button" className="login-sso" onClick={notInDemo('Signing in with Liana Technologies')}>
              <img src={googleIcon} alt="" width={20} height={20} />
              <span>Continue: Liana Technologies</span>
            </button>
          </form>
        ) : (
          <form className="login-form" onSubmit={signIn} noValidate>
            <div className="login-heading">
              <h1>Enter Your Password</h1>
              <p>Enter your password for Liana to continue to LianaSurvey Web</p>
            </div>
            <div className="login-fields">
              <div className="login-email">
                <span>{email.trim()}</span>
                <button type="button" className="login-link" onClick={editEmail} aria-label="Edit email address">
                  Edit
                </button>
              </div>
              <div className="login-password">
                <label className="visually-hidden" htmlFor="login-password">Password</label>
                <input
                  ref={passwordInput}
                  id="login-password"
                  className="login-input"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Password*"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? 'login-error' : undefined}
                />
                <button
                  type="button"
                  className="login-show"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                >
                  <Icon path={showPassword ? EYE_OFF : EYE} size={24} strokeWidth={1.6} />
                </button>
              </div>
            </div>
            {error ? <p id="login-error" className="login-error" role="alert">{error}</p> : null}
            <button type="button" className="login-link login-reset" onClick={notInDemo('Resetting the password')}>
              Reset password
            </button>
            <button type="submit" className="login-button" disabled={busy}>Continue</button>
          </form>
        )}
      </main>
      <button type="button" className="login-link login-privacy" onClick={notInDemo('The privacy policy')}>
        Privacy Policy
      </button>
    </div>
  );
}
