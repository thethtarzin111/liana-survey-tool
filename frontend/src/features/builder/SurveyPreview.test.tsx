import { fireEvent, render, screen, within } from '@testing-library/react';
import type { Question, ReaderOptions } from '../../api/client';
import { ACCENT_SWATCHES, BACKGROUND_SWATCHES } from './branding';
import { CustomPreview, PreviewQuestion, TemplatePreview } from './SurveyPreview';

const ON: ReaderOptions = { comment_field: true, show_results: true, contact_opt_in: true };
const BRAND = { accent: ACCENT_SWATCHES[2].hex, background: BACKGROUND_SWATCHES[3].hex, logoUrl: null };
const q = (kind: Question['kind'], prompt: string, options: string[] = [], required = false): Question =>
  ({ id: `${kind}-${prompt}`, survey_id: 's1', position: 1, kind, prompt, options, required });

const preview = () => screen.getByRole('region', { name: 'Preview' });
const pick = (name: string) => fireEvent.click(within(preview()).getByRole('button', { name }));

function renderThumbs(props: Partial<Parameters<typeof TemplatePreview>[0]> = {}) {
  render(
    <TemplatePreview
      type="thumbs" question="How was this newsletter?" reasons={['Too long', 'Too often']} extras={[]}
      thanks="Thanks! See you next month." options={ON} {...BRAND} {...props}
    />,
  );
}

test('the preview has the prototype heading and the thumbs screens', () => {
  renderThumbs();
  expect(within(preview()).getByRole('heading', { name: 'Preview' })).toBeInTheDocument();
  expect(preview()).toHaveTextContent('This is how respondents will see your survey');
  const screens = within(within(preview()).getByRole('group', { name: 'Preview screen' })).getAllByRole('button');
  expect(screens.map((s) => s.textContent)).toEqual(['Email block', 'Thank-you: Good / Loved it', 'Thank-you: Not for me']);
});

test('the email block shows the question and the one-tap answers', () => {
  renderThumbs();
  expect(preview()).toHaveTextContent('Bottom of the newsletter');
  expect(within(preview()).getByText('How was this newsletter?')).toBeInTheDocument();
  for (const word of ['Not for me', 'Good', 'Loved it']) expect(within(preview()).getByText(word)).toBeInTheDocument();
  expect(preview()).toHaveTextContent('One tap. Anonymous unless you ask to be contacted.');
});

test('the Good / Loved it page follows the reader options and thank-you message', () => {
  const { unmount } = render(
    <TemplatePreview type="thumbs" question="Q" reasons={[]} extras={[]} thanks="Thanks! See you." options={ON} {...BRAND} />,
  );
  pick('Thank-you: Good / Loved it');
  expect(preview()).toHaveTextContent('Thanks! You and 31% of readers loved it.');
  expect(preview()).toHaveTextContent('Thanks! See you.');
  expect(preview()).toHaveTextContent('Tell us more (optional)');
  expect(within(preview()).getByText('Customer logo')).toBeInTheDocument();
  unmount();

  render(
    <TemplatePreview
      type="thumbs" question="Q" reasons={[]} extras={[]} thanks=""
      options={{ ...ON, show_results: false, comment_field: false }} {...BRAND} logoUrl="/logo.png"
    />,
  );
  pick('Thank-you: Good / Loved it');
  expect(within(preview()).getByText('Thanks!')).toBeInTheDocument();
  expect(preview()).not.toHaveTextContent('31% of readers');
  expect(preview()).not.toHaveTextContent('Tell us more');
  expect(within(preview()).getByRole('img', { name: 'Logo' })).toHaveAttribute('src', '/logo.png');
});

test('the Not for me page shows the reasons, comment field and contact opt-in', () => {
  renderThumbs({ extras: [q('text', 'Anything to add?')] });
  pick('Thank-you: Not for me');
  expect(within(preview()).getByText('What went wrong?')).toBeInTheDocument();
  expect(within(preview()).getByText('Too long')).toBeInTheDocument();
  expect(preview()).toHaveTextContent('Anything else? (optional)');
  expect(preview()).toHaveTextContent('Contact me about this by email');
  expect(within(preview()).getByText('Anything to add?')).toBeInTheDocument();
  expect(preview()).toHaveTextContent('Everything here is optional. Your answer is already saved.');
});

test('survey pages use the survey colours', () => {
  renderThumbs();
  pick('Thank-you: Not for me');
  const page = preview().querySelector('.preview-page') as HTMLElement;
  expect(page.style.background).not.toBe('');
  expect(page.style.getPropertyValue('--preview-accent')).toBe(BRAND.accent);
});

test('NPS and CSAT have an email block and a survey page', () => {
  render(<TemplatePreview type="nps" question="Recommend us?" reasons={['Price']} extras={[]} thanks="" options={ON} {...BRAND} />);
  const screens = within(within(preview()).getByRole('group', { name: 'Preview screen' })).getAllByRole('button');
  expect(screens.map((s) => s.textContent)).toEqual(['Email block', 'Survey page']);
  expect(preview()).toHaveTextContent('0 Not at all likely');
  pick('Survey page');
  expect(preview()).toHaveTextContent('2 of 3');
  expect(preview()).toHaveTextContent('What is the main reason for your score?');
  expect(within(preview()).getByText('Price')).toBeInTheDocument();
});

test('CSAT shows its five words', () => {
  render(<TemplatePreview type="csat" question="Satisfied?" reasons={[]} extras={[]} thanks="" options={ON} {...BRAND} />);
  for (const word of ['Very dissatisfied', 'Neutral', 'Very satisfied']) expect(within(preview()).getByText(word)).toBeInTheDocument();
  pick('Survey page');
  expect(preview()).toHaveTextContent('What could we improve?');
});

test.each([
  ['single_choice', ['Yes', 'No'], ['Yes', 'No']],
  ['multiple_choice', ['Events', 'News'], ['Events', 'News']],
  ['reasons', ['Price'], ['Price']],
  ['dropdown', ['A'], ['Choose']],
  ['text', [], ['Short answer text']],
  ['long_text', [], ['Long answer text']],
  ['rating', [], ['1', '5']],
  ['nps', [], ['0', '10']],
  ['thumbs', [], ['Not for me', 'Loved it']],
] as const)('every answer type is previewed: %s', (kind, options, shown) => {
  render(<PreviewQuestion question={q(kind, 'The question', [...options], true)} />);
  expect(screen.getByText('The question *')).toBeInTheDocument();
  for (const text of shown) expect(screen.getByText(new RegExp(`^${text}`))).toBeInTheDocument();
});

test('a question without text is shown as Untitled question', () => {
  render(<PreviewQuestion question={q('text', '  ')} />);
  expect(screen.getByText('Untitled question')).toBeInTheDocument();
});

test('the Build your survey preview shows the title, questions, opt-in and Submit', () => {
  render(
    <CustomPreview
      title="" description="A short one" contactOptIn
      questions={[q('single_choice', 'Which topic?', ['Volunteering', 'Fundraising'], true)]} {...BRAND}
    />,
  );
  expect(within(preview()).getByText('Untitled survey')).toBeInTheDocument();
  expect(within(preview()).getByText('A short one')).toBeInTheDocument();
  expect(within(preview()).getByText('Which topic? *')).toBeInTheDocument();
  expect(within(preview()).getByText('Fundraising')).toBeInTheDocument();
  expect(preview()).toHaveTextContent('Contact me about this by email');
  expect(within(preview()).getByText('Submit')).toBeInTheDocument();
});
