import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ResultsPage } from './ResultsPage';

const surveys = [{ id:'s1',title:'Member NPS',type:'nps',status:'live',answers:10,headline:{score:'NPS +50',note:'scale'},description:null,thank_you:null,opens_at:null,comment_field:true,show_results:true,contact_opt_in:true,accent_color:'green',background_color:'white',logo_url:null }];
const summary = { survey_id:'s1',title:'Member NPS',type:'nps',status:'live',answers:10,segment:'all',segments:['members'],headline:{score:'NPS +50',note:'scale −100 to +100'},split:Array.from({length:11},(_,value)=>({value,count:value===9?10:0,percent:value===9?100:0})) };

beforeEach(() => vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => Response.json(String(input).includes('/results/') ? summary : surveys))));
afterEach(() => vi.unstubAllGlobals());

test('shows the selected survey headline, answer count and answer split', async () => {
  render(<MemoryRouter><ResultsPage /></MemoryRouter>);
  expect(await screen.findByText('+50')).toBeInTheDocument();
  expect(screen.getAllByText('10').length).toBeGreaterThan(0);
  expect(screen.getByRole('heading', { name: 'Answer split' })).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: 'In short' })).toHaveAttribute('aria-selected', 'true');
});

test('selecting a segment reloads its result', async () => {
  const fetchMock = vi.mocked(fetch);
  render(<MemoryRouter><ResultsPage /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText('Segment'), { target: { value: 'members' } });
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/results/s1?segment=members', expect.anything()));
});

test('shows an empty state when the survey has no answers', async () => {
  vi.mocked(fetch).mockImplementation(async (input) => Response.json(String(input).includes('/results/') ? { ...summary, answers:0, headline:null, split:[] } : surveys));
  render(<MemoryRouter><ResultsPage /></MemoryRouter>);
  expect(await screen.findByText('No answers yet.')).toBeInTheDocument();
});
