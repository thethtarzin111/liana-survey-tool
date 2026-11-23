import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { Template } from '../../api/client';
import { ToastProvider } from '../../components/ui';
import { TemplatePickerPage } from '../builder/TemplatePickerPage';
import { TemplatesPage } from './TemplatesPage';
import { sentence } from './templates';

function template(id: string, type: Template['type'], name: string, featured = true, extra: Partial<Template> = {}): Template {
  return {
    id, type, name, featured, own: false,
    description: `${name} description`,
    thank_you: `Thanks from ${name}`,
    questions: [
      { kind: type === 'csat' ? 'rating' : type === 'custom' ? 'single_choice' : type, prompt: `${name} question?`, options: type === 'custom' ? ['A', 'B'] : [], required: true },
      ...(type === 'custom' ? [] : [{ kind: 'reasons' as const, prompt: '', options: [`${name} reason`, 'Something else'], required: false }]),
    ],
    ...extra,
  };
}

const ALL = [
  template('t1', 'thumbs', 'Newsletter feedback'),
  template('t2', 'nps', 'Member NPS'),
  template('t3', 'thumbs', 'Event feedback'),
  template('t5', 'custom', 'Quick poll', true, { thank_you: '' }),
  template('t6', 'thumbs', 'Course feedback', false),
  template('t7', 'nps', 'Employee NPS (eNPS)', false),
  template('own1', 'nps', 'Our board NPS', false, { own: true, description: '' }),
];
const SURVEYS = [
  { id: 's1', title: 'Spring newsletter', type: 'thumbs' },
  { id: 's2', title: 'Member NPS 2026', type: 'nps' },
  { id: 'empty', title: 'Empty draft', type: 'csat' },
];
let surveys: typeof SURVEYS;
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  surveys = SURVEYS;
  fetchMock.mockReset().mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost');
    if (init?.method === 'POST' && url.pathname === '/api/v1/templates') {
      const body = JSON.parse(String(init.body));
      if (body.survey_id === 'empty') return Response.json({ detail: 'Add a question before you save the survey as a template.' }, { status: 409 });
      return Response.json(template('own2', 'thumbs', body.name, false, { own: true, description: body.description }), { status: 201 });
    }
    if (init?.method === 'POST') return Response.json({ id: 'new-survey' }, { status: 201 });
    if (url.pathname === '/api/v1/surveys') return Response.json(surveys);
    if (init?.method === 'DELETE') return new Response(null, { status: 204 });
    if (init?.method === 'PATCH') {
      const id = url.pathname.split('/').at(-1);
      return Response.json({ ...ALL.find((t) => t.id === id), ...JSON.parse(String(init.body)) });
    }
    const type = url.searchParams.get('type');
    return Response.json(ALL.filter((t) => !type || t.type === type));
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function Location() {
  const { pathname, search } = useLocation();
  return <span aria-label="Current location">{pathname + search}</span>;
}

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <ToastProvider>
        <Location />
        <Link to="/elsewhere">Leave</Link>
        <Routes>
          <Route path="/elsewhere" element={<h1>Elsewhere</h1>} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/surveys/new/template" element={<TemplatePickerPage />} />
          <Route path="/surveys/:id" element={<h1>Edit survey</h1>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

const posts = () => fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST').map(([input]) => String(input));

// --- Templates page -------------------------------------------------------------

test('the Templates page shows a card for each featured template and the organisation’s own', async () => {
  renderAt('/templates');
  const cards = within(await screen.findByRole('list', { name: 'Templates' })).getAllByRole('listitem');
  expect(cards.map((card) => within(card).getByRole('heading').textContent)).toEqual([
    'Newsletter feedback', 'Member NPS', 'Event feedback', 'Quick poll', 'Our board NPS',
  ]);
  const nps = cards[1];
  expect(within(nps).getByText('NPS survey')).toBeInTheDocument();
  expect(within(nps).getByText('Member NPS description.')).toBeInTheDocument();
  expect(nps).toHaveTextContent('Question: Member NPS question?');
  expect(within(cards[3]).getByText('Quick poll', { selector: '.badge' })).toBeInTheDocument();

  // Only the organisation's own template is marked as theirs and has actions.
  expect(within(cards[4]).getByText('Yours')).toBeInTheDocument();
  expect(within(cards[4]).getByRole('button', { name: 'Actions for template Our board NPS' })).toBeInTheDocument();
  expect(within(nps).queryByText('Yours')).not.toBeInTheDocument();
  expect(within(nps).queryByRole('button', { name: /Actions for/ })).not.toBeInTheDocument();
});

test('your own template can be renamed', async () => {
  renderAt('/templates');
  fireEvent.click(await screen.findByRole('button', { name: 'Actions for template Our board NPS' }));
  fireEvent.click(screen.getByRole('menuitem', { name: 'Rename' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Rename template' });
  const name = within(dialog).getByRole('textbox', { name: /Template name/ });
  expect(name).toHaveValue('Our board NPS');

  fireEvent.change(name, { target: { value: '   ' } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }));
  expect(within(dialog).getByText('Give the template a name')).toBeInTheDocument();

  fireEvent.change(name, { target: { value: ' Board NPS 2027 ' } });
  fireEvent.change(within(dialog).getByRole('textbox', { name: /Description/ }), { target: { value: 'Every spring' } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }));
  expect(await screen.findByRole('heading', { name: 'Board NPS 2027' })).toBeInTheDocument();
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  expect(screen.getByText('Template renamed to “Board NPS 2027”.')).toBeInTheDocument();

  const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
  expect(String(patch?.[0])).toBe('/api/v1/templates/own1');
  expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ name: 'Board NPS 2027', description: 'Every spring' });
});

test('a failed rename keeps the dialog open with the reason', async () => {
  renderAt('/templates');
  fireEvent.click(await screen.findByRole('button', { name: 'Actions for template Our board NPS' }));
  fireEvent.click(screen.getByRole('menuitem', { name: 'Rename' }));
  fetchMock.mockResolvedValueOnce(Response.json({ detail: 'Built-in templates cannot be changed.' }, { status: 403 }));
  const dialog = screen.getByRole('alertdialog', { name: 'Rename template' });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('Built-in templates cannot be changed.');
});

test('your own template can be deleted after confirming', async () => {
  renderAt('/templates');
  fireEvent.click(await screen.findByRole('button', { name: 'Actions for template Our board NPS' }));
  fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Delete “Our board NPS”?' });
  expect(dialog).toHaveTextContent('Surveys made from it stay as they are.');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Delete template' }));
  expect(await screen.findByText('“Our board NPS” was deleted.')).toBeInTheDocument();
  const deletes = fetchMock.mock.calls.filter(([, init]) => init?.method === 'DELETE').map(([input]) => String(input));
  expect(deletes).toEqual(['/api/v1/templates/own1']);
  // The list is loaded again.
  await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => !init?.method)).toHaveLength(2));
});

test('Use template creates a draft and opens it', async () => {
  renderAt('/templates');
  fireEvent.click(await screen.findByRole('button', { name: 'Use template Member NPS' }));
  expect(await screen.findByRole('heading', { name: 'Edit survey' })).toBeInTheDocument();
  expect(posts()).toEqual(['/api/v1/templates/t2/surveys']);
  expect(screen.getByLabelText('Current location')).toHaveTextContent('/surveys/new-survey');
  expect(screen.getByText('Draft saved')).toBeInTheDocument();
});

test('a failed Use template shows an error and allows another try', async () => {
  renderAt('/templates');
  const button = await screen.findByRole('button', { name: 'Use template Quick poll' });
  fetchMock.mockResolvedValueOnce(new Response('', { status: 500 }));
  fireEvent.click(button);
  expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t create the survey. Please try again.');
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(await screen.findByRole('heading', { name: 'Edit survey' })).toBeInTheDocument();
});

// --- Pick a template --------------------------------------------------------------

test('Pick a template lists the chosen type and shows what the first one contains', async () => {
  renderAt('/surveys/new/template?type=nps');
  expect(screen.getByRole('heading', { name: 'Pick a template' })).toBeInTheDocument();
  const options = within(await screen.findByRole('group', { name: 'Templates' })).getAllByRole('button');
  expect(options.map((o) => o.querySelector('strong')?.textContent)).toEqual(['Member NPS', 'Employee NPS (eNPS)', 'Our board NPS']);
  expect(options[0]).toHaveAttribute('aria-pressed', 'true');
  expect(options.map((o) => within(o).queryByText('Yours') !== null)).toEqual([false, false, true]);
  expect(new URL(String(fetchMock.mock.calls[0][0]), 'http://x').searchParams.get('type')).toBe('nps');

  const contents = screen.getByRole('region', { name: 'What the template contains' });
  expect(contents).toHaveTextContent('Member NPS question?');
  expect(within(contents).getByText('Member NPS reason')).toBeInTheDocument();
  expect(contents).toHaveTextContent('Thanks from Member NPS');
  expect(screen.getByRole('button', { name: 'NPS survey' })).toHaveAttribute('aria-pressed', 'true');
});

test('picking another template updates the contents', async () => {
  renderAt('/surveys/new/template?type=nps');
  fireEvent.click(await screen.findByRole('button', { name: /Employee NPS \(eNPS\)/ }));
  expect(screen.getByRole('region', { name: 'What the template contains' })).toHaveTextContent('Employee NPS (eNPS) question?');
  expect(screen.getByRole('button', { name: /Employee NPS \(eNPS\)/ })).toHaveAttribute('aria-pressed', 'true');
});

test('the Survey type switch shows that type’s templates', async () => {
  renderAt('/surveys/new/template?type=nps');
  await screen.findByRole('group', { name: 'Templates' });
  fireEvent.click(screen.getByRole('button', { name: 'Thumbs rating' }));
  await waitFor(() => expect(screen.getByLabelText('Current location')).toHaveTextContent('type=thumbs'));
  const options = within(await screen.findByRole('group', { name: 'Templates' })).getAllByRole('button');
  expect(options.map((o) => o.querySelector('strong')?.textContent)).toEqual(['Newsletter feedback', 'Event feedback', 'Course feedback']);
});

test('Continue creates the draft from the picked template', async () => {
  renderAt('/surveys/new/template?type=thumbs');
  fireEvent.click(await screen.findByRole('button', { name: /Event feedback/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Continue to edit and preview' }));
  expect(await screen.findByRole('heading', { name: 'Edit survey' })).toBeInTheDocument();
  expect(posts()).toEqual(['/api/v1/templates/t3/surveys']);
});

test('an unknown type falls back to thumbs', async () => {
  renderAt('/surveys/new/template?type=custom');
  expect(await screen.findByRole('button', { name: /Newsletter feedback/ })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Thumbs rating' })).toHaveAttribute('aria-pressed', 'true');
});

test('a failed load can be retried', async () => {
  fetchMock.mockResolvedValueOnce(new Response('', { status: 500 }));
  renderAt('/surveys/new/template?type=nps');
  expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t load the templates.');
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByRole('button', { name: /Member NPS/ })).toBeInTheDocument();
});

test('leaving while the draft is being created keeps the user where they went', async () => {
  let finish: ((response: Response) => void) | undefined;
  renderAt('/surveys/new/template?type=nps');
  await screen.findByRole('button', { name: /Member NPS/ });
  fetchMock.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  fireEvent.click(screen.getByRole('button', { name: 'Continue to edit and preview' }));
  fireEvent.click(screen.getByRole('link', { name: 'Leave' }));
  await waitFor(() => expect(finish).toBeDefined());
  finish!(Response.json({ id: 'late-survey' }, { status: 201 }));
  await waitFor(() => expect(posts()).toHaveLength(1));
  expect(screen.getByRole('heading', { name: 'Elsewhere' })).toBeInTheDocument();
  expect(screen.getByLabelText('Current location')).toHaveTextContent('/elsewhere');
  expect(screen.queryByText('Draft saved')).not.toBeInTheDocument();
});

test('descriptions end with exactly one full stop', () => {
  expect(sentence('One tap at the end of a newsletter')).toBe('One tap at the end of a newsletter.');
  expect(sentence('Already a sentence.')).toBe('Already a sentence.');
  expect(sentence('Really?')).toBe('Really?');
});


// --- Create template ------------------------------------------------------------

test('Create template saves one of the organisation’s surveys as a template', async () => {
  renderAt('/templates');
  fireEvent.click(await screen.findByRole('button', { name: 'Create template' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Create template' });
  const survey = await within(dialog).findByRole('combobox', { name: 'Survey' });
  const name = within(dialog).getByRole('textbox', { name: /Template name/ });
  expect(within(survey).getAllByRole('option').map((o) => o.textContent)).toEqual([
    'Spring newsletter (Thumbs rating)', 'Member NPS 2026 (NPS survey)', 'Empty draft (CSAT survey)',
  ]);
  expect(name).toHaveValue('Spring newsletter');

  // The name follows the chosen survey until the user types their own.
  fireEvent.change(survey, { target: { value: 's2' } });
  expect(name).toHaveValue('Member NPS 2026');
  fireEvent.change(name, { target: { value: 'Yearly NPS' } });
  fireEvent.change(survey, { target: { value: 's1' } });
  expect(name).toHaveValue('Yearly NPS');

  fireEvent.change(within(dialog).getByRole('textbox', { name: /Description/ }), { target: { value: ' For spring ' } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Save template' }));
  expect(await screen.findByText('“Yearly NPS” is saved in Templates.')).toBeInTheDocument();
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  const post = fetchMock.mock.calls.find(([input, init]) => String(input) === '/api/v1/templates' && init?.method === 'POST');
  expect(JSON.parse(String(post?.[1]?.body))).toEqual({ survey_id: 's1', name: 'Yearly NPS', description: 'For spring' });
  // The list is loaded again, so the new template appears.
  const listLoads = () => fetchMock.mock.calls.filter(([input, init]) => String(input) === '/api/v1/templates' && !init?.method).length;
  await waitFor(() => expect(listLoads()).toBe(2));
});

test('Create template shows why a survey cannot be saved', async () => {
  renderAt('/templates');
  fireEvent.click(await screen.findByRole('button', { name: 'Create template' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Create template' });
  fireEvent.change(await within(dialog).findByRole('combobox', { name: 'Survey' }), { target: { value: 'empty' } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Save template' }));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('Add a question before you save the survey as a template.');
});

test('Create template without any surveys sends the user to Create survey', async () => {
  surveys = [];
  renderAt('/templates');
  fireEvent.click(await screen.findByRole('button', { name: 'Create template' }));
  const dialog = screen.getByRole('alertdialog', { name: 'Create template' });
  expect(await within(dialog).findByText(/Create a survey first, then save it as a template/)).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Create survey' }));
  expect(screen.getByLabelText('Current location')).toHaveTextContent('/surveys/new');
});
