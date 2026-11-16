import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Question, Survey } from '../../api/client';
import { ToastProvider } from '../../components/ui';
import { BuilderPage } from './BuilderPage';

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
  const body = init?.body ? JSON.parse(String(init.body)) : undefined;
  const renumber = () => { questions = questions.map((x, i) => ({ ...x, position: i + 1 })); };
  if (path === SURVEY_URL && method === 'GET') return Response.json(survey);
  if (path === SURVEY_URL && method === 'PATCH') {
    survey = { ...survey, ...body, ...(body.title ? { title: body.title.trim() } : {}), ...('thank_you' in body ? { thank_you: body.thank_you.trim() || null } : {}) };
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
  survey = { id: 's1', title: 'Member NPS', description: null, thank_you: 'Thank you. This takes our member work forward.', type: 'nps', status: 'draft', comment_field: true, show_results: true, contact_opt_in: true };
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
  expect(await screen.findByRole('textbox', { name: 'Question' })).toHaveValue('How likely are you to recommend Example Members Association?');
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
  for (const word of ['Not for me', 'Good', 'Loved it']) expect(screen.getByText(word)).toBeInTheDocument();
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
