import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { FrontPage } from './FrontPage';

const user = { user_id: 'u', tenant_id: 't', tenant_name: 'Example', name: 'Anna Virtanen', email: 'anna@example.org' };
function renderPage(surveys: unknown[]) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => Response.json(String(input).endsWith('/me') ? user : surveys)));
  return render(<MemoryRouter><FrontPage /></MemoryRouter>);
}
afterEach(() => vi.unstubAllGlobals());

test('counts all answered surveys while limiting latest results to three', async () => {
  renderPage(Array.from({ length: 10 }, (_, index) => ({
    id: String(index), title: `Survey ${index}`, type: 'nps', status: 'live', answers: 1,
    headline: { score: `NPS +${index}`, note: 'scale' },
  })));
  await screen.findByRole('heading', { name: 'Overall statistics' });
  expect(screen.getByText('With results').parentElement).toHaveTextContent('10');
  expect(screen.getAllByRole('link', { name: 'See results' })).toHaveLength(3);
});

test('shows getting-started steps and empty-state actions to a new user', async () => {
  renderPage([]);
  expect(await screen.findByRole('heading', { name: 'Get started with LianaSurvey' })).toBeInTheDocument();
  expect(screen.getByText('Publish and share it')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Browse templates' })).toHaveAttribute('href', '/templates');
});

test('summarises surveys, results, contact requests and news', async () => {
  renderPage([{ id:'s1',title:'Member pulse',description:null,thank_you:null,type:'nps',status:'live',opens_at:null,answers:42,headline:{score:'NPS +31',note:'scale −100 to +100'},comment_field:true,show_results:true,contact_opt_in:true,accent_color:'green',background_color:'white',logo_url:null }]);
  expect(await screen.findByRole('heading', { name: 'Overall statistics' })).toBeInTheDocument();
  expect(screen.getByText('NPS +31')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Asked to be contacted' })).toBeInTheDocument();
  expect(screen.getByRole('table', { name: 'Your surveys' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'News and inspiration' })).toBeInTheDocument();
});
