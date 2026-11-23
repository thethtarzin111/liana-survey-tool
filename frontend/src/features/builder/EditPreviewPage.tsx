import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { ApiError, api, type Question, type QuestionInput, type QuestionKind, type ReaderOptions, type Survey, type SurveyType } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { PublishActions, PublishDialog } from '../publish/PublishDialog';
import { Button, ButtonLink, Card, Checkbox, InfoTip, Select, TextArea, TextField, useToast } from '../../components/ui';
import { AnswerTypeControls } from './AnswerTypeControls';
import { BrandingFields } from './BrandingFields';
import { FORMAT_HINT } from './FormattedText';
import { TemplatePreview } from './SurveyPreview';
import { ANSWER_TYPES, changesForType, newOptionText } from './answerTypes';
import { useSavedQuestions } from './useSavedQuestions';
import './builder.css';

// Texts follow the prototype's "Edit and preview" screen.
const SCALE_KIND: Record<Exclude<SurveyType, 'custom'>, QuestionKind> = { thumbs: 'thumbs', nps: 'nps', csat: 'rating' };
const SCALE_WORDS: Record<Exclude<SurveyType, 'custom'>, string[]> = {
  thumbs: ['Not for me', 'Good', 'Loved it'],
  nps: ['0 to 10', 'Detractors 0–6', 'Passives 7–8', 'Promoters 9–10'],
  csat: ['1 to 5', 'Satisfied = 4–5'],
};
const REASON_LABEL: Record<Exclude<SurveyType, 'custom'>, string> = {
  thumbs: 'Reasons for “Not for me”',
  nps: 'Reasons readers can pick (question 2)',
  csat: 'Improvement topics (question 2)',
};
const MANY_EXTRAS = 3;
/** The reader options, with the prototype's labels and tips. */
const READER_OPTIONS: { key: keyof ReaderOptions; label: string; tip: string }[] = [
  { key: 'comment_field', label: 'Optional comment field', tip: '“Tell us more” after any answer' },
  { key: 'show_results', label: 'Show results to readers', tip: 'Appears after about 10 answers' },
  {
    key: 'contact_opt_in',
    label: '"Contact me about this by email" opt-in',
    tip: 'Answers stay anonymous unless the reader ticks it. You choose what happens next in the Follow-up step.',
  },
];
const readerOptionsOf = (s: Survey): ReaderOptions =>
  ({ comment_field: s.comment_field, show_results: s.show_results, contact_opt_in: s.contact_opt_in });
/** What "+ Add question" adds to the extra questions, as in the prototype. */
const NEW_EXTRA: QuestionInput = { kind: 'single_choice', prompt: '', options: ['Option 1', 'Option 2'], required: false };
const DRAFT_SAVE_ERROR = 'We couldn’t save your draft. Please try again.';

type FieldErrors = { title?: string; reader_title?: string; description?: string; thank_you?: string };

function validationErrors(name: string, readerTitle: string, description: string, thanks: string): FieldErrors {
  if (!name.trim()) return { title: 'Give your survey a name' };
  return {
    ...(name.trim().length > 200 ? { title: 'Name must be 200 characters or fewer' } : {}),
    ...(readerTitle.trim().length > 80 ? { reader_title: 'Title must be 80 characters or fewer' } : {}),
    ...(description.trim().length > 1000 ? { description: 'Description must be 1000 characters or fewer' } : {}),
    ...(thanks.trim().length > 500 ? { thank_you: 'Thank-you message must be 500 characters or fewer' } : {}),
  };
}

function apiErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError) || !error.body || typeof error.body !== 'object' || !('detail' in error.body)) return {};
  const detail = error.body.detail;
  const fields: FieldErrors = {};
  if (!Array.isArray(detail)) return fields;
  for (const item of detail as { loc?: unknown; msg?: unknown }[]) {
    const field: unknown = Array.isArray(item?.loc) ? item.loc.at(-1) : undefined;
    if ((field === 'title' || field === 'reader_title' || field === 'description' || field === 'thank_you') && typeof item.msg === 'string') {
      fields[field] = item.msg;
    }
  }
  return fields;
}

/** Text that is saved when leaving the field, and follows the saved value. */
function useSavedText(saved: string) {
  const [text, setText] = useState(saved);
  useEffect(() => setText(saved), [saved]);
  return [text, setText] as const;
}

function ReasonChip({ text: saved, index, onlyOne, onSave, onRemove }: {
  text: string; index: number; onlyOne: boolean;
  onSave: (text: string) => void; onRemove: () => void;
}) {
  const [text, setText] = useSavedText(saved);
  return (
    <span className="chip-edit">
      <input
        aria-label={`Reason ${index + 1}`}
        maxLength={200}
        size={Math.max(3, text.length)}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onBlur={() => {
          if (!text.trim()) setText(saved);
          else if (text.trim() !== saved) onSave(text.trim());
        }}
      />
      <button type="button" className="chip-remove" aria-label={`Remove reason ${index + 1}`} disabled={onlyOne} onClick={onRemove}>
        ×
      </button>
    </span>
  );
}

function ExtraQuestion({ question, number, busy, onSave, onChangeOptions, onDelete }: {
  question: Question; number: number; busy: boolean;
  onSave: (changes: Partial<QuestionInput>) => void;
  onChangeOptions: (change: (options: string[]) => string[]) => void;
  onDelete: () => void;
}) {
  const [text, setText] = useSavedText(question.prompt);
  const name = `Extra question ${number}`;
  return (
    <div role="group" aria-label={name} className="extra-question">
      <div className="question-card-head">
        <TextField
          label={`Question ${number}`}
          placeholder="Untitled question"
          maxLength={500}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onBlur={() => { if (text.trim() !== question.prompt) onSave({ prompt: text.trim() }); }}
        />
        <Select
          label="Answer type"
          options={ANSWER_TYPES}
          value={question.kind}
          disabled={busy}
          onChange={(event) => {
            const kind = event.target.value as QuestionKind;
            if (kind !== question.kind) onSave(changesForType({ ...question, prompt: text }, kind));
          }}
        />
      </div>
      <AnswerTypeControls question={question} number={number} name={name} onChangeOptions={onChangeOptions} />
      <div className="question-actions">
        <Checkbox label="Required" checked={question.required} disabled={busy} onChange={() => onSave({ required: !question.required })} />
        <Button variant="ghost" size="sm" aria-label={`Delete extra question ${number}`} disabled={busy} onClick={onDelete}>
          Delete
        </Button>
      </div>
    </div>
  );
}

/** "Edit and preview": the editor for thumbs, NPS and CSAT surveys, usually made from a template. */
export function EditPreviewPage({ survey, onSaved }: { survey: Survey; onSaved: (survey: Survey) => void }) {
  const toast = useToast();
  const type = survey.type as Exclude<SurveyType, 'custom'>;
  const { questions, setQuestions, loadError, retry, busy, save, update, updateOptions } = useSavedQuestions(survey.id);
  const [name, setName] = useState(survey.title);
  const [readerTitle, setReaderTitle] = useState(survey.reader_title ?? '');
  const [description, setDescription] = useState(survey.description ?? '');
  const [thanks, setThanks] = useState(survey.thank_you ?? '');
  const [options, setOptions] = useState<ReaderOptions>(() => readerOptionsOf(survey));
  const [accent, setAccent] = useState(survey.accent_color);
  const [background, setBackground] = useState(survey.background_color);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saveError, setSaveError] = useState('');
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const savingRef = useRef(false);
  const mounted = useRef(true);
  const reasonsLabel = useId();
  const formId = useId();

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const all = questions ?? [];
  // The main question is the first one, if it has the survey's scale. Older drafts
  // may have none yet: then every question is shown as an extra question, typing
  // the Question adds the main question first, and + Add reason puts the reasons
  // first (they move to second when the main question is added).
  const main = all[0]?.kind === SCALE_KIND[type] ? all[0] : undefined;
  const reasons = all.find((q) => q !== main && q.kind === 'reasons');
  const extras = all.filter((q) => q !== main && q !== reasons);
  const [questionText, setQuestionText] = useSavedText(main?.prompt ?? '');

  /** Adds a question and moves it to `index` (the main question first, then the reasons). */
  function insert(input: QuestionInput, index: number) {
    save(async () => {
      const added = await api.addQuestion(survey.id, input);
      const order = (await api.questions(survey.id)).map((q) => q.id).filter((id) => id !== added.id);
      order.splice(index, 0, added.id);
      setQuestions(await api.reorderQuestions(survey.id, order));
    });
  }

  function saveQuestionText() {
    if (main) {
      if (questionText.trim() !== main.prompt) update(main, { prompt: questionText.trim() });
    } else if (questionText.trim()) {
      // Older drafts may not have their main question yet.
      insert({ kind: SCALE_KIND[type], prompt: questionText.trim(), options: [], required: true }, 0);
    }
  }

  async function saveDraft(event: FormEvent) {
    event.preventDefault();
    await saveChanges(false);
  }

  /** Saves the form. Returns false when it could not be saved (errors are shown). */
  async function saveChanges(quiet: boolean): Promise<boolean> {
    if (savingRef.current) return false;
    const found = validationErrors(name, readerTitle, description, thanks);
    setErrors(found);
    setSaveError('');
    if (Object.keys(found).length) return false;

    const changes: {
      title?: string;
      reader_title?: string;
      description?: string;
      thank_you?: string;
      accent_color?: string;
      background_color?: string;
    } & Partial<ReaderOptions> = {};
    if (accent !== survey.accent_color) changes.accent_color = accent;
    if (background !== survey.background_color) changes.background_color = background;
    if (name.trim() !== survey.title) changes.title = name;
    if (readerTitle.trim() !== (survey.reader_title ?? '')) changes.reader_title = readerTitle;
    if (description.trim() !== (survey.description ?? '')) changes.description = description;
    if (thanks.trim() !== (survey.thank_you ?? '')) changes.thank_you = thanks;
    for (const { key } of READER_OPTIONS) {
      if (options[key] !== survey[key]) changes[key] = options[key];
    }
    if (!Object.keys(changes).length) {
      if (!quiet) toast('Saved as draft');
      return true;
    }
    savingRef.current = true;
    setSaving(true);
    try {
      const saved = await api.updateSurvey(survey.id, changes);
      if (!mounted.current) return false;
      setName(saved.title);
      setReaderTitle(saved.reader_title ?? '');
      setDescription(saved.description ?? '');
      setThanks(saved.thank_you ?? '');
      setOptions(readerOptionsOf(saved));
      setAccent(saved.accent_color);
      setBackground(saved.background_color);
      onSaved(saved);
      if (!quiet) toast('Saved as draft');
      return true;
    } catch (error) {
      if (!mounted.current) return false;
      const fromApi = apiErrors(error);
      setErrors(fromApi);
      if (!Object.keys(fromApi).length) setSaveError(DRAFT_SAVE_ERROR);
      return false;
    } finally {
      savingRef.current = false;
      if (mounted.current) setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Edit and preview"
        actions={
          <div className="survey-builder-actions">
            <ButtonLink to="/surveys/new" variant="ghost">Cancel</ButtonLink>
            <Button type="submit" form={formId} loading={saving}>Save as draft</Button>
            <PublishActions survey={survey} onPublish={() => setPublishing(true)} />
          </div>
        }
      />
      <PublishDialog
        survey={publishing ? { id: survey.id, title: name.trim() || survey.title } : null}
        onClose={() => setPublishing(false)}
        beforePublish={() => saveChanges(true)}
      />
      <div className="edit-layout">
      <form id={formId} onSubmit={saveDraft} noValidate>
        <Card padded className="edit-settings">
          <section aria-label="Settings" className="edit-settings-body">
            <TextField
              label="Name (only you see this)"
              value={name}
              error={errors.title}
              disabled={saving}
              onChange={(event) => { setName(event.target.value); setErrors((e) => ({ ...e, title: undefined })); }}
            />
            <TextField
              label="Title readers see (optional)"
              hint="Shown at the top of the survey link page. Without it, the page starts with the question."
              maxLength={80}
              value={readerTitle}
              error={errors.reader_title}
              disabled={saving}
              onChange={(event) => { setReaderTitle(event.target.value); setErrors((e) => ({ ...e, reader_title: undefined })); }}
            />
            <TextArea
              label="Description (optional)"
              hint={`A line or two under the title on the survey link page. ${FORMAT_HINT}`}
              rows={2}
              maxLength={1000}
              value={description}
              error={errors.description}
              disabled={saving}
              onChange={(event) => { setDescription(event.target.value); setErrors((e) => ({ ...e, description: undefined })); }}
            />
            {loadError ? (
              <div className="survey-error" role="alert">
                <p>We couldn’t load the questions. Please try again.</p>
                <Button onClick={retry}>Try again</Button>
              </div>
            ) : !questions ? (
              <p role="status">Loading questions…</p>
            ) : (
              <>
                <TextField
                  label="Question"
                  maxLength={500}
                  value={questionText}
                  onChange={(event) => setQuestionText(event.target.value)}
                  onBlur={saveQuestionText}
                />
                <div className="edit-field">
                  <span className="edit-label">Answers</span>
                  <ul className="edit-scale">
                    {SCALE_WORDS[type].map((word) => <li key={word}>{word}</li>)}
                  </ul>
                  <span className="answer-hint">The scale is fixed so results can be compared over time.</span>
                </div>
                <div className="edit-field">
                  <span id={reasonsLabel} className="edit-label">{REASON_LABEL[type]}</span>
                  <div role="group" aria-labelledby={reasonsLabel} className="edit-reasons">
                    {(reasons?.options ?? []).map((reason, index, options) => (
                      <ReasonChip
                        key={`${reasons!.id}-${index}`}
                        text={reason}
                        index={index}
                        onlyOne={options.length <= 1}
                        onSave={(text) => updateOptions(reasons!.id, (current) => current.map((o, i) => (i === index ? text : o)))}
                        onRemove={() => updateOptions(reasons!.id, (current) => current.filter((_, i) => i !== index))}
                      />
                    ))}
                    <button
                      type="button"
                      className="chip edit-add-reason"
                      disabled={reasons ? reasons.options.length >= 20 : busy}
                      onClick={() => reasons
                        ? updateOptions(reasons.id, (current) => [...current, newOptionText('reasons', current)])
                        : insert({ kind: 'reasons', prompt: '', options: ['New reason'], required: false }, main ? 1 : 0)}
                    >
                      + Add reason
                    </button>
                  </div>
                  <span className="answer-hint">Click a reason to rename it. Readers pick one or more. Free text is optional.</span>
                </div>
                <div className="edit-field">
                  <span className="edit-label">Extra questions (optional)</span>
                  {extras.map((question, index) => (
                    <ExtraQuestion
                      key={question.id}
                      question={question}
                      number={index + 1}
                      busy={busy}
                      onSave={(changes) => update(question, changes)}
                      onChangeOptions={(change) => updateOptions(question.id, change)}
                      onDelete={() => save(async () => {
                        await api.deleteQuestion(survey.id, question.id);
                        setQuestions((list) => list && list.filter((q) => q.id !== question.id));
                      })}
                    />
                  ))}
                  {extras.length >= MANY_EXTRAS ? (
                    <span className="answer-hint" role="status">
                      You have {extras.length} extra questions. Every extra question means fewer people finish. Keep only the ones you will act on.
                    </span>
                  ) : null}
                  <Button
                    className="edit-add-question"
                    disabled={busy}
                    onClick={() => save(async () => {
                      const added = await api.addQuestion(survey.id, NEW_EXTRA);
                      setQuestions((list) => (list ? [...list, added] : [added]));
                    })}
                  >
                    + Add question
                  </Button>
                </div>
              </>
            )}
            <TextArea
              label="Thank-you message"
              rows={2}
              value={thanks}
              error={errors.thank_you}
              disabled={saving}
              onChange={(event) => { setThanks(event.target.value); setErrors((e) => ({ ...e, thank_you: undefined })); }}
            />
            <fieldset className="reader-options">
              <legend className="edit-label">Reader options</legend>
              {READER_OPTIONS.map(({ key, label, tip }) => (
                <div key={key} className="reader-option">
                  <Checkbox
                    label={label}
                    checked={options[key]}
                    disabled={saving}
                    onChange={() => setOptions((current) => ({ ...current, [key]: !current[key] }))}
                  />
                  <InfoTip label={`About: ${label}. ${tip}`}>{tip}</InfoTip>
                </div>
              ))}
            </fieldset>
            <div className="edit-field">
              <span className="edit-label">Brand</span>
              <span className="answer-hint">Your logo and colour are used on the survey pages respondents see. Check the Preview.</span>
              <BrandingFields
                survey={survey}
                accent={accent}
                background={background}
                onAccentChange={setAccent}
                onBackgroundChange={setBackground}
                onLogoChange={onSaved}
              />
            </div>
          </section>
        </Card>
        {saveError ? <p className="survey-save-error" role="alert">{saveError}</p> : null}
      </form>
      <TemplatePreview
        type={type}
        readerTitle={readerTitle}
        description={description}
        question={questionText}
        reasons={reasons?.options ?? []}
        reasonsPrompt={reasons?.prompt ?? ''}
        extras={extras}
        thanks={thanks}
        options={options}
        accent={accent}
        background={background}
        logoUrl={survey.logo_url}
      />
      </div>
    </>
  );
}
