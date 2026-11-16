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
    saved[index] = { ...saved[index], ...body, ...(body.prompt !== undefined ? { prompt: body.prompt.trim() } : {}) };
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
  expect(await screen.findByRole('textbox', { name: 'Question 1' })).toHaveValue('Prompt 1');
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
