import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { Template } from '../../api/client';
import { ToastProvider } from '../../components/ui';
import { TemplatePickerPage } from '../builder/TemplatePickerPage';
import { TemplatesPage } from './TemplatesPage';

function template(id: string, type: Template['type'], name: string, featured = true, extra: Partial<Template> = {}): Template {
  return {
    id, type, name, featured,
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
];
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset().mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost');
    if (init?.method === 'POST') return Response.json({ id: 'new-survey' }, { status: 201 });
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
        <Routes>
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

test('the Templates page shows a card for each featured template', async () => {
  renderAt('/templates');
  const cards = within(await screen.findByRole('list', { name: 'Templates' })).getAllByRole('listitem');
  expect(cards.map((card) => within(card).getByRole('heading').textContent)).toEqual([
    'Newsletter feedback', 'Member NPS', 'Event feedback', 'Quick poll',
  ]);
  const nps = cards[1];
  expect(within(nps).getByText('NPS survey')).toBeInTheDocument();
  expect(within(nps).getByText('Member NPS description.')).toBeInTheDocument();
  expect(nps).toHaveTextContent('Question: Member NPS question?');
  expect(within(cards[3]).getByText('Quick poll', { selector: '.badge' })).toBeInTheDocument();
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
  expect(options.map((o) => o.querySelector('strong')?.textContent)).toEqual(['Member NPS', 'Employee NPS (eNPS)']);
  expect(options[0]).toHaveAttribute('aria-pressed', 'true');
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
