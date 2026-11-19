import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { Question } from '../../api/client';
import { ToastProvider } from '../../components/ui';
import { QuestionList } from './QuestionList';

const BASE = '/api/v1/surveys/s1/questions';
const fetchMock = vi.fn<typeof fetch>();
let saved: Question[];
let nextId: number;

function question(n: number, changes: Partial<Question> = {}): Question {
  return { id: `q${n}`, survey_id: 's1', position: n, kind: 'text', prompt: `Prompt ${n}`, options: [], required: true, ...changes };
}

/** A small in-memory questions API, like survey-manager's. */
async function server(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const path = String(input);
  const method = init?.method ?? 'GET';
  const body = init?.body ? JSON.parse(String(init.body)) : undefined;
  const renumber = () => { saved = saved.map((q, i) => ({ ...q, position: i + 1 })); };
  const id = path.slice(BASE.length + 1).split('/')[0];

  if (method === 'GET' && path === BASE) return Response.json(saved);
  if (method === 'POST' && path === BASE) {
    const added = { ...question(saved.length + 1), ...body, id: `new${nextId++}`, prompt: body.prompt.trim() };
    saved = [...saved, added];
    renumber();
    return Response.json(saved.at(-1), { status: 201 });
  }
  if (method === 'PUT' && path === `${BASE}/order`) {
    saved = body.question_ids.map((qid: string) => saved.find((q) => q.id === qid));
    renumber();
    return Response.json(saved);
  }
  const index = saved.findIndex((q) => q.id === id);
  if (index < 0) return Response.json({ detail: 'Question not found' }, { status: 404 });
  if (method === 'PATCH') {
    const next = { ...saved[index], ...body, ...(body.prompt !== undefined ? { prompt: body.prompt.trim() } : {}) };
    // Like the server: types without options lose them.
    if (!['single_choice', 'multiple_choice', 'dropdown', 'reasons'].includes(next.kind)) next.options = [];
    saved[index] = next;
    return Response.json(saved[index]);
  }
  if (method === 'DELETE') {
    saved = saved.filter((q) => q.id !== id);
    renumber();
    return new Response(null, { status: 204 });
  }
  if (method === 'POST' && path.endsWith('/duplicate')) {
    saved.splice(index + 1, 0, { ...saved[index], id: `copy${nextId++}` });
    renumber();
    return Response.json(saved[index + 1], { status: 201 });
  }
  throw new Error(`Unexpected ${method} ${path}`);
}

beforeEach(() => {
  saved = [question(1), question(2), question(3)];
  nextId = 1;
  fetchMock.mockReset().mockImplementation(server);
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderList() {
  render(
    <ToastProvider>
      <QuestionList surveyId="s1" />
    </ToastProvider>,
  );
}

const prompts = () => screen.getAllByRole('textbox').map((input) => (input as HTMLInputElement).value);
const calls = (method: string) => fetchMock.mock.calls.filter(([, init]) => (init?.method ?? 'GET') === method);

test('shows each question with its number, text and actions', async () => {
  renderList();
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Question 1' })).toHaveValue('Prompt 1'));
  expect(prompts()).toEqual(['Prompt 1', 'Prompt 2', 'Prompt 3']);
  expect(screen.getByRole('textbox', { name: 'Question 2' })).toHaveAttribute('placeholder', 'Untitled question');
  expect(screen.getByRole('button', { name: 'Move question 1 up' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Move question 1 down' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Move question 3 down' })).toBeDisabled();
  expect(within(screen.getByRole('group', { name: 'Question 2' })).getByLabelText('Required')).toBeChecked();
});

test('the only question cannot be deleted', async () => {
  saved = [question(1)];
  renderList();
  expect(await screen.findByRole('button', { name: 'Delete question 1' })).toBeDisabled();
});

test('+ Add question saves a new optional multiple-choice question and focuses it', async () => {
  renderList();
  fireEvent.click(await screen.findByRole('button', { name: '+ Add question' }));
  const added = await screen.findByRole('textbox', { name: 'Question 4' });
  await waitFor(() => expect(added).toHaveFocus());
  expect(added).toHaveValue('');
  expect(within(screen.getByRole('group', { name: 'Question 4' })).getByLabelText('Required')).not.toBeChecked();
  expect(JSON.parse(String(calls('POST')[0][1]?.body))).toEqual({
    kind: 'single_choice', prompt: '', options: ['Option 1'], required: false,
  });
});

test('question text is saved when leaving the field, only if it changed', async () => {
  renderList();
  const input = await screen.findByRole('textbox', { name: 'Question 2' });
  fireEvent.blur(input);
  expect(calls('PATCH')).toHaveLength(0);

  fireEvent.change(input, { target: { value: '  How was the event?  ' } });
  fireEvent.blur(input);
  await waitFor(() => expect(input).toHaveValue('How was the event?'));
  expect(calls('PATCH')).toHaveLength(1);
  expect(calls('PATCH')[0][0]).toBe(`${BASE}/q2`);
  expect(saved[1].prompt).toBe('How was the event?');
});

test('Required is saved right away', async () => {
  renderList();
  const box = within(await screen.findByRole('group', { name: 'Question 1' })).getByLabelText('Required');
  fireEvent.click(box);
  expect(box).not.toBeChecked();
  await waitFor(() => expect(saved[0].required).toBe(false));
  expect(JSON.parse(String(calls('PATCH')[0][1]?.body))).toEqual({ required: false });
});

test('arrows move a question and save the new order', async () => {
  renderList();
  fireEvent.click(await screen.findByRole('button', { name: 'Move question 1 down' }));
  expect(prompts()).toEqual(['Prompt 2', 'Prompt 1', 'Prompt 3']);
  await waitFor(() => expect(saved.map((q) => q.id)).toEqual(['q2', 'q1', 'q3']));

  await waitFor(() => expect(screen.getByRole('button', { name: 'Move question 3 up' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Move question 3 up' }));
  await waitFor(() => expect(saved.map((q) => q.id)).toEqual(['q2', 'q3', 'q1']));
  expect(prompts()).toEqual(['Prompt 2', 'Prompt 3', 'Prompt 1']);
});

test('Duplicate puts the copy right after the question', async () => {
  renderList();
  fireEvent.click(await screen.findByRole('button', { name: 'Duplicate question 1' }));
  await waitFor(() => expect(prompts()).toEqual(['Prompt 1', 'Prompt 1', 'Prompt 2', 'Prompt 3']));
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Question 2' })).toHaveFocus());
});

test('Delete removes the question and renumbers the rest', async () => {
  renderList();
  fireEvent.click(await screen.findByRole('button', { name: 'Delete question 2' }));
  await waitFor(() => expect(prompts()).toEqual(['Prompt 1', 'Prompt 3']));
  expect(screen.getByRole('textbox', { name: 'Question 2' })).toHaveValue('Prompt 3');
  expect(saved.map((q) => q.id)).toEqual(['q1', 'q3']);
});

test('warns about long surveys above 5 questions', async () => {
  saved = [1, 2, 3, 4, 5].map((n) => question(n));
  renderList();
  await screen.findByRole('textbox', { name: 'Question 5' });
  expect(screen.queryByText(/Surveys with more than 5 questions/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '+ Add question' }));
  expect(
    await screen.findByText('You have 6 questions. Surveys with more than 5 questions get noticeably fewer answers.'),
  ).toBeInTheDocument();
});

test('a failed save shows an error and goes back to what is saved', async () => {
  renderList();
  await screen.findByRole('textbox', { name: 'Question 1' });
  fetchMock.mockImplementationOnce(async () => new Response('', { status: 500 }));
  fireEvent.click(screen.getByRole('button', { name: 'Move question 1 down' }));
  expect(await screen.findByText('We couldn’t save your question. Please try again.')).toBeInTheDocument();
  await waitFor(() => expect(prompts()).toEqual(['Prompt 1', 'Prompt 2', 'Prompt 3']));
});

test('buttons wait while a change is being saved', async () => {
  let finish: (() => void) | undefined;
  renderList();
  await screen.findByRole('textbox', { name: 'Question 1' });
  fetchMock.mockImplementationOnce((input, init) => new Promise((resolve) => {
    finish = () => resolve(server(input, init));
  }));
  fireEvent.click(screen.getByRole('button', { name: 'Delete question 3' }));
  expect(screen.getByRole('button', { name: '+ Add question' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Delete question 1' })).toBeDisabled();
  await waitFor(() => expect(finish).toBeDefined());
  finish!();
  await waitFor(() => expect(screen.getByRole('button', { name: '+ Add question' })).toBeEnabled());
  expect(calls('DELETE')).toHaveLength(1);
});

test('a failed load can be retried', async () => {
  fetchMock.mockImplementationOnce(async () => new Response('', { status: 500 }));
  renderList();
  expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t load the questions.');
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByRole('textbox', { name: 'Question 1' })).toBeInTheDocument();
});

// --- Answer types (#31) ---------------------------------------------------------

const card = (n: number) => within(screen.getByRole('group', { name: `Question ${n}` }));

test('the Answer type dropdown lists the eight types and saves a change', async () => {
  renderList();
  await screen.findByRole('group', { name: 'Question 1' });
  const select = card(1).getByRole('combobox', { name: 'Answer type' }) as HTMLSelectElement;
  expect([...select.options].map((o) => o.textContent)).toEqual([
    'Multiple choice', 'Checkboxes', 'Dropdown', 'Short answer', 'Paragraph',
    'Rating 1–5 (CSAT)', 'NPS 0–10', 'Reason bubbles',
  ]);
  expect(select).toHaveValue('text');
  expect(card(1).getByText('Short answer text')).toBeInTheDocument();

  fireEvent.change(select, { target: { value: 'long_text' } });
  expect(await card(1).findByText('Long answer text')).toBeInTheDocument();
  await waitFor(() => expect(saved[0].kind).toBe('long_text'));
  expect(JSON.parse(String(calls('PATCH')[0][1]?.body))).toEqual({ kind: 'long_text' });
});

test('choice types show their options with + Add option and remove buttons', async () => {
  saved = [question(1, { kind: 'single_choice', options: ['Yes', 'No'] })];
  renderList();
  await screen.findByRole('group', { name: 'Question 1' });
  const first = await screen.findByRole('textbox', { name: 'Question 1, option 1' });
  expect(first).toHaveValue('Yes');

  fireEvent.click(card(1).getByRole('button', { name: '+ Add option' }));
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Question 1, option 3' })).toHaveValue('Option 3'));
  await waitFor(() => expect(saved[0].options).toEqual(['Yes', 'No', 'Option 3']));

  fireEvent.click(card(1).getByRole('button', { name: 'Remove option 1' }));
  await waitFor(() => expect(saved[0].options).toEqual(['No', 'Option 3']));
  expect(screen.getByRole('textbox', { name: 'Question 1, option 1' })).toHaveValue('No');
});

test('option text is saved when leaving the field, and an emptied option goes back', async () => {
  saved = [question(1, { kind: 'dropdown', options: ['Yes', 'No'] })];
  renderList();
  await screen.findByRole('group', { name: 'Question 1' });
  const option = await screen.findByRole('textbox', { name: 'Question 1, option 2' });
  fireEvent.change(option, { target: { value: '  Not really ' } });
  fireEvent.blur(option);
  await waitFor(() => expect(saved[0].options).toEqual(['Yes', 'Not really']));

  fireEvent.change(option, { target: { value: '   ' } });
  fireEvent.blur(option);
  expect(option).toHaveValue('Not really');
  expect(calls('PATCH')).toHaveLength(1);
});

test('the last option cannot be removed', async () => {
  saved = [question(1, { kind: 'multiple_choice', options: ['Only one'] })];
  renderList();
  await screen.findByRole('group', { name: 'Question 1' });
  expect(await screen.findByRole('button', { name: 'Remove option 1' })).toBeDisabled();
});

test('Reason bubbles get common reasons, + Add reason and their hint', async () => {
  saved = [question(1, { kind: 'single_choice', options: ['Option 1', 'Option 2'] })];
  renderList();
  await screen.findByRole('group', { name: 'Question 1' });
  fireEvent.change(await card(1).findByRole('combobox', { name: 'Answer type' }), { target: { value: 'reasons' } });
  await waitFor(() => expect(saved[0].options).toEqual(['Price', 'Quality', 'Customer service', 'Something else']));
  expect(card(1).getByRole('button', { name: '+ Add reason' })).toBeInTheDocument();
  expect(card(1).getByText('Respondents tap one or more bubbles. Each bubble becomes a category in Top reasons.')).toBeInTheDocument();
});

test('NPS shows the fixed scale and fills in the standard question', async () => {
  saved = [question(1, { prompt: '' })];
  renderList();
  await screen.findByRole('group', { name: 'Question 1' });
  fireEvent.change(await card(1).findByRole('combobox', { name: 'Answer type' }), { target: { value: 'nps' } });
  await waitFor(() => expect(saved[0].prompt).toBe('How likely are you to recommend us to a friend or colleague?'));
  expect(screen.getByRole('textbox', { name: 'Question 1' })).toHaveValue('How likely are you to recommend us to a friend or colleague?');
  expect(card(1).getByText(/^Standard NPS scale: 0 Not at all likely to 10 Extremely likely\./)).toBeInTheDocument();
  expect(card(1).getByText('10')).toBeInTheDocument();
});

test('CSAT rating shows the 1–5 scale and its hint', async () => {
  saved = [question(1, { kind: 'rating' })];
  renderList();
  await screen.findByRole('group', { name: 'Question 1' });
  expect(await card(1).findByText('Standard CSAT scale: 1 Very dissatisfied to 5 Very satisfied. Score = % of 4–5 answers.')).toBeInTheDocument();
  expect(card(1).queryByRole('button', { name: '+ Add option' })).not.toBeInTheDocument();
});

test('switching from a scale to a choice type starts with Option 1', async () => {
  saved = [question(1, { kind: 'rating' })];
  renderList();
  await screen.findByRole('group', { name: 'Question 1' });
  fireEvent.change(await card(1).findByRole('combobox', { name: 'Answer type' }), { target: { value: 'multiple_choice' } });
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Question 1, option 1' })).toHaveValue('Option 1'));
  await waitFor(() => expect(saved[0]).toMatchObject({ kind: 'multiple_choice', options: ['Option 1'] }));
});

test('removing an option right after renaming another keeps both changes', async () => {
  saved = [question(1, { kind: 'single_choice', options: ['Yes', 'No', 'Maybe'] })];
  renderList();
  const second = await screen.findByRole('textbox', { name: 'Question 1, option 2' });
  fireEvent.change(second, { target: { value: 'Not really' } });
  fireEvent.blur(second);
  const remove = card(1).getByRole('button', { name: 'Remove option 3' });
  expect(remove).toBeEnabled();
  fireEvent.click(remove);
  await waitFor(() => expect(saved[0].options).toEqual(['Yes', 'Not really']));
});
