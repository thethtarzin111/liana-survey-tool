import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { BuilderPage } from '../features/builder/BuilderPage';
import { LivePage } from '../features/publish/LivePage';
import { CreateSurveyPage } from '../features/builder/CreateSurveyPage';
import { TemplatePickerPage } from '../features/builder/TemplatePickerPage';
import { FrontPage } from '../features/front/FrontPage';
import { IntegrationsPage } from '../features/integrations/IntegrationsPage';
import { LoginPage } from '../features/login/LoginPage';
import { ResultsPage } from '../features/results/ResultsPage';
import { SettingsPage } from '../features/settings/SettingsPage';
import { SupportPage } from '../features/support/SupportPage';
import { SurveysPage } from '../features/surveys/SurveysPage';
import { TemplatesPage } from '../features/templates/TemplatesPage';
import { Header } from './Header';

// Dev-only component preview; the import is dropped from production builds.
const ComponentsPage = import.meta.env.DEV
  ? lazy(() => import('../dev/ComponentsPage').then((m) => ({ default: m.ComponentsPage })))
  : null;
import { Sidebar } from './Sidebar';

export function App() {
  const { pathname } = useLocation();
  // The login page has no header or sidebar.
  return pathname === '/login' ? <LoginPage /> : <SignedInApp />;
}

/** Goes to the login page when the gateway says there is no session (demo server only). */
function useLoginWhenSignedOut() {
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    let alive = true;
    api.me().catch((err) => {
      if (alive && err instanceof ApiError && err.status === 401) {
        navigate(`/login?next=${encodeURIComponent(pathname + search)}`, { replace: true });
      }
    });
    return () => {
      alive = false;
    };
    // Checked once, when the app opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

function SignedInApp() {
  useLoginWhenSignedOut();
  // On narrow screens the sidebar is a drawer opened from the header menu button.
  const [navOpen, setNavOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const { pathname } = useLocation();

  // Close the drawer after navigating.
  useEffect(() => setNavOpen(false), [pathname]);

  // Escape closes the drawer and puts focus back on the menu button.
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setNavOpen(false);
        menuButton.current?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [navOpen]);

  return (
    <div className="shell">
      <Header navOpen={navOpen} onToggleNav={() => setNavOpen((o) => !o)} menuButtonRef={menuButton} />
      <div className="body">
        {navOpen ? <div className="scrim" aria-hidden="true" onClick={() => setNavOpen(false)} /> : null}
        <Sidebar open={navOpen} />
        <main className="main">
          <Routes>
            <Route path="/" element={<FrontPage />} />
            <Route path="/surveys" element={<SurveysPage />} />
            <Route path="/surveys/new" element={<CreateSurveyPage />} />
            <Route path="/surveys/new/template" element={<TemplatePickerPage />} />
            <Route path="/surveys/:id" element={<BuilderPage />} />
            <Route path="/surveys/:id/live" element={<LivePage />} />
            <Route path="/results" element={<ResultsPage />} />
            <Route path="/responses" element={<Navigate to="/results?tab=responses" replace />} />
            {/* The old Contact requests page: its requests are a filter in Responses now. */}
            <Route path="/contact-requests" element={<Navigate to="/results?tab=responses&group=contact" replace />} />
            <Route path="/templates" element={<TemplatesPage />} />
            <Route path="/integrations" element={<IntegrationsPage />} />
            <Route path="/support" element={<SupportPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            {ComponentsPage ? (
              <Route
                path="/dev/components"
                element={
                  <Suspense fallback={null}>
                    <ComponentsPage />
                  </Suspense>
                }
              />
            ) : null}
            <Route path="*" element={<p>Page not found.</p>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
