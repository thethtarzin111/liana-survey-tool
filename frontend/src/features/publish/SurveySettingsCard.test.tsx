import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Survey } from '../../api/client';
import { ToastProvider } from '../../components/ui';
import { DEFAULT_ACCENT, DEFAULT_BACKGROUND } from '../builder/branding';
import { closesAtFromDay, today } from './closeDate';
import { SurveySettingsCard } from './SurveySettingsCard';

const survey: Survey = {
  id: 'nps-1', title: 'Member NPS', description: null, thank_you: null, type: 'nps', status: 'live',
  public_url: 'http://localhost:8000/r/abc', published_at: '2026-11-18T09:00:00Z',
  comment_field: true, show_results: true, contact_opt_in: true,
  accent_color: DEFAULT_ACCENT, background_color: DEFAULT_BACKGROUND, logo_url: null,
  closes_at: null, response_limit: null, notify_on_response: false, language: 'en',
};

function dayFromToday(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return today(d);
}

const fetchMock = vi.fn<typeof fetch>();
const onSaved = vi.fn<(saved: Survey) => void>();
let current: Survey = survey;

beforeEach(() => {
  onSaved.mockReset();
  fetchMock.mockReset().mockImplementation(async (_url, init) =>
    Response.json({ ...current, ...JSON.parse(String(init?.body)) }),
  );
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderCard(saved: Survey = survey) {
  current = saved;
  render(
    <ToastProvider>
      <MemoryRouter>
        <SurveySettingsCard survey={saved} onSaved={onSaved} />
      </MemoryRouter>
    </ToastProvider>,
  );
}

const save = () => screen.getByRole('button', { name: 'Save settings' });
const sentBody = () => JSON.parse(String(fetchMock.mock.calls[0][1]?.body));

test('saves the close day, the limit and "notify me"', async () => {
  renderCard();
  expect(save()).toBeDisabled();
  const day = dayFromToday(30);
  fireEvent.change(screen.getByLabelText('Closes on'), { target: { value: day } });
  fireEvent.change(screen.getByLabelText('Response limit'), { target: { value: '500' } });
  fireEvent.click(screen.getByLabelText('Notify me of new responses by email'));
  fireEvent.click(save());

  expect(await screen.findByText('Settings saved')).toBeInTheDocument();
  expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/surveys/nps-1');
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'PATCH' });
  expect(sentBody()).toEqual({ closes_at: closesAtFromDay(day), response_limit: 500, notify_on_response: true });
  expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ response_limit: 500 }));
  expect(save()).toBeDisabled();
});

test('emptying the fields removes the close date and the limit', async () => {
  renderCard({ ...survey, closes_at: closesAtFromDay(dayFromToday(10)), response_limit: 200 });
  expect(screen.getByLabelText('Closes on')).toHaveValue(dayFromToday(10));
  expect(screen.getByLabelText('Response limit')).toHaveValue(200);
  fireEvent.change(screen.getByLabelText('Closes on'), { target: { value: '' } });
  fireEvent.change(screen.getByLabelText('Response limit'), { target: { value: '' } });
  fireEvent.click(save());
  await screen.findByText('Settings saved');
  expect(sentBody()).toEqual({ closes_at: null, response_limit: null });
});

test('a past day and a bad limit are explained and not saved', () => {
  renderCard();
  fireEvent.change(screen.getByLabelText('Closes on'), { target: { value: dayFromToday(-1) } });
  expect(screen.getByText('Pick today or a later day.')).toBeInTheDocument();
  for (const bad of ['0', '2.5', '1000001']) {
    fireEvent.change(screen.getByLabelText('Response limit'), { target: { value: bad } });
    expect(screen.getByText(/Enter a whole number from 1 to 1,000,000/)).toBeInTheDocument();
  }
  expect(screen.getByLabelText('Response limit')).toHaveAttribute('aria-invalid', 'true');
  fireEvent.click(save());
  expect(fetchMock).not.toHaveBeenCalled();
});

test('only changed settings are sent, so a past close date does not block other changes', async () => {
  const closedAt = '2026-01-15T12:30:00.000Z';
  renderCard({ ...survey, closes_at: closedAt, response_limit: 200 });
  expect(screen.queryByText('Pick today or a later day.')).not.toBeInTheDocument();
  expect(Number(new Date(`${(screen.getByLabelText('Closes on') as HTMLInputElement).min}T12:00`))).toBeLessThan(Date.now());
  fireEvent.change(screen.getByLabelText('Response limit'), { target: { value: '300' } });
  fireEvent.click(screen.getByLabelText('Notify me of new responses by email'));
  fireEvent.click(save());
  await screen.findByText('Settings saved');
  expect(sentBody()).toEqual({ response_limit: 300, notify_on_response: true });
  expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ closes_at: closedAt }));
});

test('today is a valid close day', () => {
  renderCard();
  fireEvent.change(screen.getByLabelText('Closes on'), { target: { value: dayFromToday(0) } });
  expect(screen.queryByText('Pick today or a later day.')).not.toBeInTheDocument();
  expect(save()).toBeEnabled();
});

test('an API refusal is shown with its reason', async () => {
  fetchMock.mockResolvedValue(Response.json({ detail: 'The close date must be in the future.' }, { status: 422 }));
  renderCard();
  fireEvent.change(screen.getByLabelText('Response limit'), { target: { value: '5' } });
  fireEvent.click(save());
  expect(await screen.findByRole('alert')).toHaveTextContent('The close date must be in the future.');
  expect(onSaved).not.toHaveBeenCalled();
});

test('says answers are anonymous and links to results and all surveys', () => {
  renderCard();
  expect(screen.getByText(/Answers from the public link and QR code are anonymous, unless the reader ticks “Contact me”/)).toBeInTheDocument();
  expect(screen.queryByRole('radio')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Go to results' })).toHaveAttribute('href', '/results');
  expect(screen.getByRole('link', { name: 'Back to all surveys' })).toHaveAttribute('href', '/surveys');
});

test('the survey language is shown, picked and saved on its own', async () => {
  renderCard({ ...survey, language: 'fi' });
  const language = screen.getByLabelText('Survey language');
  expect(language).toHaveValue('fi');
  expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
    'English',
    'Suomi',
    'Svenska',
  ]);
  fireEvent.change(language, { target: { value: 'sv' } });
  fireEvent.click(save());
  await screen.findByText('Settings saved');
  expect(sentBody()).toEqual({ language: 'sv' });
  expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ language: 'sv' }));
  expect(save()).toBeDisabled();
});

test('surveys without a language show English', () => {
  renderCard({ ...survey, language: undefined });
  expect(screen.getByLabelText('Survey language')).toHaveValue('en');
});

test('the privacy note says newsletter answers are linked to the contact', () => {
  renderCard();
  expect(screen.getByText(/Answers from a LianaMailer newsletter are linked to the reader’s contact/)).toBeInTheDocument();
  expect(screen.queryByLabelText(/Identified answers/)).toBeNull();
});
