import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { BuilderPage } from '../features/builder/BuilderPage';
import { LivePage } from '../features/publish/LivePage';
import { CreateSurveyPage } from '../features/builder/CreateSurveyPage';
import { TemplatePickerPage } from '../features/builder/TemplatePickerPage';
import { ContactRequestsPage } from '../features/contact-requests/ContactRequestsPage';
import { FrontPage } from '../features/front/FrontPage';
import { IntegrationsPage } from '../features/integrations/IntegrationsPage';
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
            <Route path="/contact-requests" element={<ContactRequestsPage />} />
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
