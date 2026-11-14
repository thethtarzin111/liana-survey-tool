import { Route, Routes } from 'react-router-dom';
import { BuilderPage } from '../features/builder/BuilderPage';
import { ContactRequestsPage } from '../features/contact-requests/ContactRequestsPage';
import { FrontPage } from '../features/front/FrontPage';
import { IntegrationsPage } from '../features/integrations/IntegrationsPage';
import { ResponsesPage } from '../features/responses/ResponsesPage';
import { ResultsPage } from '../features/results/ResultsPage';
import { SettingsPage } from '../features/settings/SettingsPage';
import { SupportPage } from '../features/support/SupportPage';
import { SurveysPage } from '../features/surveys/SurveysPage';
import { TemplatesPage } from '../features/templates/TemplatesPage';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export function App() {
  return (
    <div className="shell">
      <Header />
      <div className="body">
        <Sidebar />
        <main className="main">
          <Routes>
            <Route path="/" element={<FrontPage />} />
            <Route path="/surveys" element={<SurveysPage />} />
            <Route path="/surveys/new" element={<BuilderPage />} />
            <Route path="/results" element={<ResultsPage />} />
            <Route path="/responses" element={<ResponsesPage />} />
            <Route path="/contact-requests" element={<ContactRequestsPage />} />
            <Route path="/templates" element={<TemplatesPage />} />
            <Route path="/integrations" element={<IntegrationsPage />} />
            <Route path="/support" element={<SupportPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<p>Page not found.</p>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
