import { useState, type CSSProperties, type ReactNode } from 'react';
import type { Question, ReaderOptions, SurveyType } from '../../api/client';
import { SegmentedControl } from '../../components/ui';
import { TEXT_HINTS } from './answerTypes';

// Texts follow the prototype's "Preview" panels on Edit and preview and Build your survey.
const CSAT_WORDS = ['Very dissatisfied', 'Dissatisfied', 'Neutral', 'Satisfied', 'Very satisfied'];
const NPS = Array.from({ length: 11 }, (_, n) => n);

type Brand = { accent: string; background: string; logoUrl: string | null };

/** The page colours respondents get: the survey background and its accent for buttons. */
function frameStyle({ accent, background }: Brand): CSSProperties {
  return { background, ['--preview-accent' as string]: accent };
}

function Logo({ logoUrl }: { logoUrl: string | null }) {
  return logoUrl
    ? <img className="preview-logo" src={logoUrl} alt="Logo" />
    : <span className="preview-logo preview-logo-empty">Customer logo</span>;
}

function Scale({ numbers, picked, words }: { numbers: number[]; picked?: number; words?: string[] }) {
  return (
    <div className={`preview-scale${numbers.length > 5 ? ' preview-scale-nps' : ''}`}>
      {numbers.map((n, i) => (
        <span key={n} className={n === picked ? 'is-picked' : undefined}>
          {n}
          {words ? <small>{words[i]}</small> : null}
        </span>
      ))}
    </div>
  );
}

/** One question as respondents see it, for every answer type. */
export function PreviewQuestion({ question }: { question: Pick<Question, 'kind' | 'prompt' | 'options' | 'required'> }) {
  const label = `${question.prompt.trim() || 'Untitled question'}${question.required ? ' *' : ''}`;
  let answer: ReactNode;
  switch (question.kind) {
    case 'single_choice':
    case 'multiple_choice':
      answer = (
        <ul className="preview-options">
          {question.options.map((option) => (
            <li key={option}>
              <span className={`preview-mark preview-mark-${question.kind}`} aria-hidden="true" />
              {option}
            </li>
          ))}
        </ul>
      );
      break;
    case 'reasons':
      answer = <ul className="preview-chips">{question.options.map((option) => <li key={option}>{option}</li>)}</ul>;
      break;
    case 'dropdown':
      answer = <span className="preview-input">Choose <span aria-hidden="true">▾</span></span>;
      break;
    case 'text':
    case 'long_text':
      answer = <span className={`preview-input preview-${question.kind}`}>{TEXT_HINTS[question.kind]}</span>;
      break;
    case 'rating':
      answer = <Scale numbers={[1, 2, 3, 4, 5]} />;
      break;
    case 'nps':
      answer = <Scale numbers={NPS} />;
      break;
    case 'thumbs':
      answer = <ThumbsButtons />;
      break;
  }
  return (
    <div className="preview-question">
      <strong>{label}</strong>
      {answer}
    </div>
  );
}

function ThumbsButtons() {
  return (
    <div className="preview-thumbs">
      <span>Not for me</span>
      <span>Good</span>
      <span>Loved it</span>
    </div>
  );
}

function Panel({ tabs, children }: { tabs?: ReactNode; children: ReactNode }) {
  return (
    <section className="preview-panel card" aria-label="Preview">
      <div className="preview-head">
        <h2>Preview</h2>
        <p>This is how respondents will see your survey</p>
      </div>
      {tabs}
      {children}
    </section>
  );
}

type TemplateProps = Brand & {
  type: Exclude<SurveyType, 'custom'>;
  question: string;
  reasons: string[];
  extras: Question[];
  thanks: string;
  options: ReaderOptions;
};

/** The preview next to "Edit and preview" (thumbs, NPS and CSAT surveys). */
export function TemplatePreview({ type, question, reasons, extras, thanks, options, ...brand }: TemplateProps) {
  const screens = type === 'thumbs'
    ? [{ value: 'email', label: 'Email block' }, { value: 'good', label: 'Thank-you: Good / Loved it' }, { value: 'bad', label: 'Thank-you: Not for me' }]
    : [{ value: 'email', label: 'Email block' }, { value: 'survey', label: 'Survey page' }];
  const [screen, setScreen] = useState('email');
  const current = screens.some((s) => s.value === screen) ? screen : 'email';
  const shown = question.trim() || 'Untitled question';
  const extraQuestions = extras.length
    ? <div className="preview-extras">{extras.map((q) => <PreviewQuestion key={q.id} question={q} />)}</div>
    : null;

  let body: ReactNode;
  if (current === 'email') {
    body = (
      <div className="preview-email">
        <span className="preview-hint">Bottom of the newsletter</span>
        <strong>{shown}</strong>
        {type === 'thumbs' ? <ThumbsButtons /> : null}
        {type === 'nps' ? (
          <>
            <Scale numbers={NPS} />
            <div className="preview-ends"><span>0 Not at all likely</span><span>10 Extremely likely</span></div>
          </>
        ) : null}
        {type === 'csat' ? <Scale numbers={[1, 2, 3, 4, 5]} words={CSAT_WORDS} /> : null}
        <span className="preview-hint">One tap. Anonymous unless you ask to be contacted.</span>
      </div>
    );
  } else if (current === 'good') {
    body = (
      <div className="preview-page" style={frameStyle(brand)}>
        <Logo logoUrl={brand.logoUrl} />
        {options.show_results ? (
          <>
            <strong>Thanks! You and 31% of readers loved it.</strong>
            <div className="preview-results" aria-hidden="true"><span style={{ width: '31%' }} /><span style={{ width: '53%' }} /></div>
            <div className="preview-ends"><span>31% Loved it</span><span>53% Good</span><span>16% Not for me</span></div>
          </>
        ) : <strong>Thanks!</strong>}
        {extraQuestions}
        {thanks.trim() ? <span>{thanks.trim()}</span> : null}
        {options.comment_field ? <span className="preview-input">Tell us more (optional)</span> : null}
      </div>
    );
  } else if (current === 'bad') {
    body = (
      <div className="preview-page" style={frameStyle(brand)}>
        <Logo logoUrl={brand.logoUrl} />
        <strong>What went wrong?</strong>
        <ul className="preview-chips">{reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        {options.comment_field ? <span className="preview-input">Anything else? (optional)</span> : null}
        {extraQuestions}
        {options.contact_opt_in ? <span className="preview-contact"><span className="preview-mark preview-mark-multiple_choice" aria-hidden="true" />Contact me about this by email</span> : null}
        <span className="preview-hint">Everything here is optional. Your answer is already saved.</span>
      </div>
    );
  } else {
    body = (
      <div className="preview-page" style={frameStyle(brand)}>
        <div className="preview-topbar"><Logo logoUrl={brand.logoUrl} /><span className="preview-hint">2 of 3</span></div>
        <strong>{shown}</strong>
        {type === 'nps' ? (
          <>
            <Scale numbers={NPS} picked={9} />
            <div className="preview-ends"><span>0 Not at all likely</span><span>10 Extremely likely</span></div>
          </>
        ) : <Scale numbers={[1, 2, 3, 4, 5]} words={CSAT_WORDS} picked={4} />}
        <span className="preview-hint">Your answer from the email is saved. Tap another one to change it.</span>
        <strong>{type === 'nps' ? 'What is the main reason for your score?' : 'What could we improve?'}</strong>
        <ul className="preview-chips">{reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        {extraQuestions}
      </div>
    );
  }

  return (
    <Panel tabs={<SegmentedControl label="Preview screen" options={screens} value={current} onChange={setScreen} />}>
      <div className="preview-frame">{body}</div>
    </Panel>
  );
}

type CustomProps = Brand & {
  title: string;
  description: string;
  questions: Question[];
  contactOptIn: boolean;
};

/** The preview next to "Build your survey" (custom surveys). */
export function CustomPreview({ title, description, questions, contactOptIn, ...brand }: CustomProps) {
  return (
    <Panel>
      <div className="preview-frame">
        <div className="preview-page" style={frameStyle(brand)}>
          {brand.logoUrl ? <Logo logoUrl={brand.logoUrl} /> : null}
          <div className="preview-title">
            <strong>{title.trim() || 'Untitled survey'}</strong>
            {description.trim() ? <span>{description.trim()}</span> : null}
          </div>
          {questions.map((q) => <PreviewQuestion key={q.id} question={q} />)}
          {contactOptIn ? <span className="preview-contact"><span className="preview-mark preview-mark-multiple_choice" aria-hidden="true" />Contact me about this by email</span> : null}
          <span className="preview-submit">Submit</span>
        </div>
      </div>
    </Panel>
  );
}
