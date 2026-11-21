import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Question, Survey } from '../../api/client';
import { ToastProvider } from '../../components/ui';
import { BuilderPage } from './BuilderPage';
import { ACCENT_SWATCHES, BACKGROUND_SWATCHES, DEFAULT_ACCENT, DEFAULT_BACKGROUND } from './branding';

const SURVEY_URL = '/api/v1/surveys/s1';
const QUESTIONS_URL = `${SURVEY_URL}/questions`;
const fetchMock = vi.fn<typeof fetch>();
let survey: Survey;
let questions: Question[];
let nextId: number;

const q = (id: string, kind: Question['kind'], prompt: string, options: string[] = [], required = true): Question =>
  ({ id, survey_id: 's1', position: 0, kind, prompt, options, required });

/** A small in-memory survey and questions API. */
async function server(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const path = String(input);
  const method = init?.method ?? 'GET';
  const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined;
  const renumber = () => { questions = questions.map((x, i) => ({ ...x, position: i + 1 })); };
  if (path === SURVEY_URL && method === 'GET') return Response.json(survey);
  if (path === SURVEY_URL && method === 'PATCH') {
    survey = { ...survey, ...body, ...(body.title ? { title: body.title.trim() } : {}), ...('thank_you' in body ? { thank_you: body.thank_you.trim() || null } : {}) };
    return Response.json(survey);
  }
  if (path === `${SURVEY_URL}/logo` && method === 'PUT') {
    survey = { ...survey, logo_url: `${SURVEY_URL}/logo?v=${nextId++}` };
    return Response.json(survey);
  }
  if (path === `${SURVEY_URL}/logo` && method === 'DELETE') {
    survey = { ...survey, logo_url: null };
    return new Response(null, { status: 204 });
  }
  if (path === `${SURVEY_URL}/publish` && method === 'POST') {
    survey = { ...survey, status: 'live', public_url: 'http://localhost:8000/r/token' };
    return Response.json(survey);
  }
  if (path === QUESTIONS_URL && method === 'GET') return Response.json(questions);
  if (path === QUESTIONS_URL && method === 'POST') {
    const added = { ...q(`new${nextId++}`, body.kind, body.prompt.trim(), body.options, body.required) };
    questions = [...questions, added];
    renumber();
    return Response.json(questions.at(-1), { status: 201 });
  }
  if (path === `${QUESTIONS_URL}/order`) {
    questions = body.question_ids.map((id: string) => questions.find((x) => x.id === id));
    renumber();
    return Response.json(questions);
  }
  const id = path.slice(QUESTIONS_URL.length + 1);
  const index = questions.findIndex((x) => x.id === id);
  if (method === 'PATCH') {
    questions[index] = { ...questions[index], ...body, ...(body.prompt !== undefined ? { prompt: body.prompt.trim() } : {}) };
    return Response.json(questions[index]);
  }
  if (method === 'DELETE') {
    questions = questions.filter((x) => x.id !== id);
    renumber();
    return new Response(null, { status: 204 });
  }
  throw new Error(`Unexpected ${method} ${path}`);
}

beforeEach(() => {
  survey = { id: 's1', title: 'Member NPS', description: null, thank_you: 'Thank you. This takes our member work forward.', type: 'nps', status: 'draft', comment_field: true, show_results: true, contact_opt_in: true, accent_color: DEFAULT_ACCENT, background_color: DEFAULT_BACKGROUND, logo_url: null };
  questions = [
    q('main', 'nps', 'How likely are you to recommend Example Members Association?'),
    q('reasons', 'reasons', '', ['Events and activities', 'Membership fee', 'Something else'], false),
  ];
  nextId = 1;
  fetchMock.mockReset().mockImplementation(server);
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/surveys/s1']}>
      <ToastProvider>
        <Routes>
          <Route path="/surveys/:id" element={<BuilderPage />} />
          <Route path="/surveys/new" element={<h1>Create survey</h1>} />
          <Route path="/surveys/:id/live" element={<h1>Live page</h1>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

const reasonsGroup = () => screen.getByRole('group', { name: 'Reasons readers can pick (question 2)' });
const patches = (url: string) => fetchMock.mock.calls.filter(([input, init]) => String(input) === url && init?.method === 'PATCH');

test('NPS, thumbs and CSAT surveys open on Edit and preview with their settings', async () => {
  renderPage();
  expect(await screen.findByRole('heading', { name: 'Edit and preview' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Build your survey' })).not.toBeInTheDocument();
  expect(screen.getByLabelText('Name (only you see this)')).toHaveValue('Member NPS');
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Question' })).toHaveValue('How likely are you to recommend Example Members Association?'));
  expect(screen.getByText('Detractors 0–6')).toBeInTheDocument();
  expect(screen.getByText('The scale is fixed so results can be compared over time.')).toBeInTheDocument();
  expect(within(reasonsGroup()).getByRole('textbox', { name: 'Reason 2' })).toHaveValue('Membership fee');
  expect(screen.getByLabelText('Thank-you message')).toHaveValue('Thank you. This takes our member work forward.');
});

test('thumbs surveys show their three answers and reason label', async () => {
  survey = { ...survey, type: 'thumbs' };
  questions = [q('main', 'thumbs', 'How was this newsletter?'), q('reasons', 'reasons', '', ['Too long'], false)];
  renderPage();
  expect(await screen.findByRole('group', { name: 'Reasons for “Not for me”' })).toBeInTheDocument();
  const settings = screen.getByRole('region', { name: 'Settings' });
  for (const word of ['Not for me', 'Good', 'Loved it']) expect(within(settings).getByText(word)).toBeInTheDocument();
});

test('the question text is saved when leaving the field', async () => {
  renderPage();
  const field = await screen.findByRole('textbox', { name: 'Question' });
  fireEvent.change(field, { target: { value: '  Would you recommend us?  ' } });
  fireEvent.blur(field);
  await waitFor(() => expect(questions[0].prompt).toBe('Would you recommend us?'));
});

test('reasons can be renamed, added and removed', async () => {
  renderPage();
  const second = await within(await screen.findByRole('group', { name: 'Reasons readers can pick (question 2)' })).findByRole('textbox', { name: 'Reason 2' });
  fireEvent.change(second, { target: { value: 'Price' } });
  fireEvent.blur(second);
  await waitFor(() => expect(questions[1].options).toEqual(['Events and activities', 'Price', 'Something else']));

  fireEvent.click(within(reasonsGroup()).getByRole('button', { name: '+ Add reason' }));
  await waitFor(() => expect(questions[1].options.at(-1)).toBe('New reason'));

  fireEvent.click(within(reasonsGroup()).getByRole('button', { name: 'Remove reason 1' }));
  await waitFor(() => expect(questions[1].options).toEqual(['Price', 'Something else', 'New reason']));
});

test('the last reason cannot be removed', async () => {
  questions[1] = { ...questions[1], options: ['Only one'] };
  renderPage();
  expect(await screen.findByRole('button', { name: 'Remove reason 1' })).toBeDisabled();
});

test('extra questions can be added, edited and deleted, with a warning at three', async () => {
  renderPage();
  const add = await screen.findByRole('button', { name: '+ Add question' });
  fireEvent.click(add);
  const extra = await screen.findByRole('group', { name: 'Extra question 1' });
  expect(within(extra).getByRole('textbox', { name: 'Extra question 1, option 2' })).toHaveValue('Option 2');
  expect(within(extra).getByLabelText('Required')).not.toBeChecked();
  expect(questions.at(-1)).toMatchObject({ kind: 'single_choice', options: ['Option 1', 'Option 2'], required: false });

  fireEvent.change(within(extra).getByRole('combobox', { name: 'Answer type' }), { target: { value: 'long_text' } });
  expect(await within(extra).findByText('Long answer text')).toBeInTheDocument();

  await waitFor(() => expect(add).toBeEnabled());
  fireEvent.click(add);
  await screen.findByRole('group', { name: 'Extra question 2' });
  expect(screen.queryByText(/extra questions\. Every extra question/)).not.toBeInTheDocument();
  await waitFor(() => expect(add).toBeEnabled());
  fireEvent.click(add);
  expect(await screen.findByText(
    'You have 3 extra questions. Every extra question means fewer people finish. Keep only the ones you will act on.',
  )).toBeInTheDocument();

  await waitFor(() => expect(add).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Delete extra question 1' }));
  await waitFor(() => expect(screen.queryByRole('group', { name: 'Extra question 3' })).not.toBeInTheDocument());
  expect(questions.map((x) => x.id)).toEqual(['main', 'reasons', 'new2', 'new3']);
});

test('Save as draft saves the name and thank-you message', async () => {
  renderPage();
  fireEvent.change(await screen.findByLabelText('Name (only you see this)'), { target: { value: 'Member NPS 2026' } });
  fireEvent.change(screen.getByLabelText('Thank-you message'), { target: { value: 'Thanks!' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
  expect(await screen.findByText('Saved as draft')).toBeInTheDocument();
  expect(JSON.parse(String(patches(SURVEY_URL)[0][1]?.body))).toEqual({ title: 'Member NPS 2026', thank_you: 'Thanks!' });
  expect(survey).toMatchObject({ title: 'Member NPS 2026', thank_you: 'Thanks!' });
});

test('the title readers see and the description are saved and shown on the Link page (#105)', async () => {
  renderPage();
  fireEvent.change(await screen.findByLabelText('Title readers see (optional)'), { target: { value: 'How are we doing?' } });
  fireEvent.change(screen.getByLabelText('Description (optional)'), { target: { value: 'One minute.' } });
  const previewPanel = screen.getByRole('region', { name: 'Preview' });
  fireEvent.click(within(previewPanel).getByRole('button', { name: 'Link page' }));
  expect(previewPanel).toHaveTextContent('How are we doing?');
  expect(previewPanel).toHaveTextContent('One minute.');
  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
  expect(await screen.findByText('Saved as draft')).toBeInTheDocument();
  expect(JSON.parse(String(patches(SURVEY_URL)[0][1]?.body))).toEqual({ reader_title: 'How are we doing?', description: 'One minute.' });
});

test('a too long reader title blocks saving', async () => {
  renderPage();
  fireEvent.change(await screen.findByLabelText('Title readers see (optional)'), { target: { value: 'x'.repeat(81) } });
  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
  expect(await screen.findByText('Title must be 80 characters or fewer')).toBeInTheDocument();
  expect(patches(SURVEY_URL)).toHaveLength(0);
});

test('an empty name blocks saving', async () => {
  renderPage();
  fireEvent.change(await screen.findByLabelText('Name (only you see this)'), { target: { value: '  ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
  expect(await screen.findByText('Give your survey a name')).toBeInTheDocument();
  expect(patches(SURVEY_URL)).toHaveLength(0);
});

test('a draft without its main question gets one when the question is typed', async () => {
  questions = [q('reasons', 'reasons', '', ['Price'], false)];
  renderPage();
  const field = await screen.findByRole('textbox', { name: 'Question' });
  expect(field).toHaveValue('');
  fireEvent.change(field, { target: { value: 'How likely are you to recommend us?' } });
  fireEvent.blur(field);
  await waitFor(() => expect(questions.map((x) => x.kind)).toEqual(['nps', 'reasons']));
  expect(questions[0]).toMatchObject({ prompt: 'How likely are you to recommend us?', required: true });
});

test('Cancel goes back to Create survey', async () => {
  renderPage();
  fireEvent.click(await screen.findByRole('link', { name: 'Cancel' }));
  expect(screen.getByRole('heading', { name: 'Create survey' })).toBeInTheDocument();
});

test('removing a reason right after renaming another keeps both changes', async () => {
  renderPage();
  const second = await within(await screen.findByRole('group', { name: 'Reasons readers can pick (question 2)' })).findByRole('textbox', { name: 'Reason 2' });
  fireEvent.change(second, { target: { value: 'Price' } });
  // Clicking × moves focus out of the chip first, which saves the rename.
  fireEvent.blur(second);
  const remove = within(reasonsGroup()).getByRole('button', { name: 'Remove reason 1' });
  expect(remove).toBeEnabled();
  fireEvent.click(remove);
  await waitFor(() => expect(questions[1].options).toEqual(['Price', 'Something else']));
  expect(within(reasonsGroup()).getAllByRole('textbox').map((input) => (input as HTMLInputElement).value)).toEqual(['Price', 'Something else']);
});

test('reader options show their tips and are saved with Save as draft', async () => {
  renderPage();
  const group = await screen.findByRole('group', { name: 'Reader options' });
  const boxes = within(group).getAllByRole('checkbox');
  expect(boxes.map((box) => box.closest('label')?.textContent)).toEqual([
    'Optional comment field', 'Show results to readers', '"Contact me about this by email" opt-in',
  ]);
  for (const box of boxes) expect(box).toBeChecked();
  expect(within(group).getByText('Appears after about 10 answers')).toBeInTheDocument();
  expect(within(group).getByRole('button', { name: /^About: "Contact me about this by email" opt-in\. Answers stay anonymous/ })).toBeInTheDocument();

  fireEvent.click(within(group).getByLabelText('Show results to readers'));
  fireEvent.click(within(group).getByLabelText('"Contact me about this by email" opt-in'));
  expect(patches(SURVEY_URL)).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
  expect(await screen.findByText('Saved as draft')).toBeInTheDocument();
  expect(JSON.parse(String(patches(SURVEY_URL)[0][1]?.body))).toEqual({ show_results: false, contact_opt_in: false });
  expect(survey).toMatchObject({ comment_field: true, show_results: false, contact_opt_in: false });
});

test('saved reader options are shown when the survey opens', async () => {
  survey = { ...survey, comment_field: false, show_results: true, contact_opt_in: false };
  renderPage();
  const group = await screen.findByRole('group', { name: 'Reader options' });
  expect(within(group).getByLabelText('Optional comment field')).not.toBeChecked();
  expect(within(group).getByLabelText('Show results to readers')).toBeChecked();
  expect(within(group).getByLabelText('"Contact me about this by email" opt-in')).not.toBeChecked();
});

// --- Branding (#67) ------------------------------------------------------------

const brand = () => screen.getByRole('group', { name: 'Accent colour' });
const backgroundGroup = () => screen.getByRole('group', { name: 'Background colour' });

test('accent and background swatches are saved with Save as draft', async () => {
  renderPage();
  await screen.findByRole('group', { name: 'Accent colour' });
  expect(within(brand()).getByRole('button', { name: 'Teal' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(within(brand()).getByRole('button', { name: 'Plum' }));
  fireEvent.click(within(backgroundGroup()).getByRole('button', { name: 'Sand' }));
  expect(within(brand()).getByRole('button', { name: 'Plum' })).toHaveAttribute('aria-pressed', 'true');
  expect(within(brand()).getByLabelText('Hex code')).toHaveValue(ACCENT_SWATCHES[2].hex);
  expect(patches(SURVEY_URL)).toHaveLength(0);

  fireEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
  expect(await screen.findByText('Saved as draft')).toBeInTheDocument();
  expect(JSON.parse(String(patches(SURVEY_URL)[0][1]?.body))).toEqual({
    accent_color: ACCENT_SWATCHES[2].hex, background_color: BACKGROUND_SWATCHES[3].hex, // Plum, Sand
  });
});

test('a typed hex code is used, and a bad one is refused', async () => {
  renderPage();
  const hex = within(await screen.findByRole('group', { name: 'Accent colour' })).getByLabelText('Hex code');
  fireEvent.change(hex, { target: { value: '1b4f9c' } });
  fireEvent.blur(hex);
  expect(within(brand()).getByRole('button', { name: 'Blue' })).toHaveAttribute('aria-pressed', 'true');
  expect(hex).toHaveValue(ACCENT_SWATCHES[1].hex);

  fireEvent.change(hex, { target: { value: 'blue' } });
  fireEvent.keyDown(hex, { key: 'Enter' });
  expect(await screen.findByText('Use a 6-digit hex code, like #2B6450.')).toBeInTheDocument();
  expect(hex).toHaveValue(ACCENT_SWATCHES[1].hex);
});

test('a light accent shows the contrast warning', async () => {
  renderPage();
  const hex = within(await screen.findByRole('group', { name: 'Accent colour' })).getByLabelText('Hex code');
  fireEvent.change(hex, { target: { value: BACKGROUND_SWATCHES[1].hex } }); // light grey as an accent
  fireEvent.blur(hex);
  expect(await screen.findByText(/^White text on this colour is hard to read/)).toBeInTheDocument();
});

test('a logo is uploaded straight away and can be removed', async () => {
  renderPage();
  expect(await screen.findByText('No logo yet')).toBeInTheDocument();
  const input = screen.getByLabelText('Upload logo') as HTMLInputElement;
  const file = new File(['<svg/>'], 'logo.svg', { type: 'image/svg+xml' });
  fireEvent.change(input, { target: { files: [file] } });
  expect(await screen.findByRole('img', { name: 'Your logo' })).toHaveAttribute('src', expect.stringContaining('/logo?v='));
  const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT');
  expect(put?.[1]?.headers).toMatchObject({ 'Content-Type': 'image/svg+xml' });
  expect(put?.[1]?.body).toBe(file);

  fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
  expect(await screen.findByText('No logo yet')).toBeInTheDocument();
  expect(survey.logo_url).toBeNull();
});

test('a wrong file type is refused before uploading', async () => {
  renderPage();
  const input = (await screen.findByLabelText('Upload logo')) as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(['GIF'], 'logo.gif', { type: 'image/gif' })] } });
  expect(await screen.findByText('Choose an image file: PNG, JPG or SVG.')).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false);
});


// --- Live preview (#46) -------------------------------------------------------

test('the preview updates while editing', async () => {
  renderPage();
  const previewPanel = await screen.findByRole('region', { name: 'Preview' });
  expect(within(previewPanel).getByText('How likely are you to recommend Example Members Association?')).toBeInTheDocument();

  fireEvent.change(await screen.findByRole('textbox', { name: 'Question' }), { target: { value: 'Would you recommend us?' } });
  expect(within(previewPanel).getByText('Would you recommend us?')).toBeInTheDocument();

  fireEvent.click(within(previewPanel).getByRole('button', { name: 'Survey page' }));
  expect(within(previewPanel).getByText('Membership fee')).toBeInTheDocument();
  const page = previewPanel.querySelector('.preview-page') as HTMLElement;
  fireEvent.click(within(screen.getByRole('group', { name: 'Accent colour' })).getByRole('button', { name: 'Blue' }));
  expect(page.style.getPropertyValue('--preview-accent')).toBe(ACCENT_SWATCHES[1].hex);
});

test('Publish saves unsaved changes first, then opens the live page (#117)', async () => {
  renderPage();
  fireEvent.change(await screen.findByLabelText('Name (only you see this)'), { target: { value: 'Member NPS 2026' } });
  fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Publish “Member NPS 2026”?' });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Publish' }));
  expect(await screen.findByRole('heading', { name: 'Live page' })).toBeInTheDocument();
  const calls = fetchMock.mock.calls.map(([input, init]) => `${init?.method ?? 'GET'} ${String(input)}`);
  expect(calls.indexOf(`PATCH ${SURVEY_URL}`)).toBeLessThan(calls.indexOf(`POST ${SURVEY_URL}/publish`));
  expect(survey.title).toBe('Member NPS 2026');
});

test('a name error stops publishing', async () => {
  renderPage();
  fireEvent.change(await screen.findByLabelText('Name (only you see this)'), { target: { value: '  ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
  fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Publish' }));
  await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
  expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith('/publish'))).toBe(false);
  expect(screen.queryByRole('heading', { name: 'Live page' })).not.toBeInTheDocument();
});

test('live surveys get Share instead of Publish', async () => {
  survey = { ...survey, status: 'live' };
  renderPage();
  expect(await screen.findByRole('link', { name: 'Share' })).toHaveAttribute('href', '/surveys/s1/live');
  expect(screen.queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument();
});
