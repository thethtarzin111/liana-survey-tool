import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError, api, type Question, type Survey } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Button, ButtonLink, Card, Disclosure, TextArea, TextField, useToast } from '../../components/ui';
import { BrandingFields } from './BrandingFields';
import { FORMAT_HINT } from './FormattedText';
import { EditPreviewPage } from './EditPreviewPage';
import { PublishActions, PublishDialog } from '../publish/PublishDialog';
import { saveTexts } from './saveTexts';
import { QuestionList } from './QuestionList';
import { CustomPreview } from './SurveyPreview';
import './builder.css';

/** Same cap as the API's survey title (#115). */
const SURVEY_TITLE_MAX = 80;

type FieldErrors = { title?: string; description?: string };

function validationErrors(title: string, description: string): FieldErrors {
  if (!title.trim()) return { title: 'Give your survey a title' };
  return {
    ...(title.trim().length > 200 ? { title: 'Survey title must be 200 characters or fewer' } : {}),
    ...(description.trim().length > 1000
      ? { description: 'Description must be 1000 characters or fewer' }
      : {}),
  };
}

function apiErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError) || !error.body || typeof error.body !== 'object') return {};
  const detail = 'detail' in error.body ? error.body.detail : null;
  if (!Array.isArray(detail)) return {};
  const fields: FieldErrors = {};
  for (const item of detail) {
    if (!item || typeof item !== 'object' || !('loc' in item) || !('msg' in item)) continue;
    const loc = Array.isArray(item.loc) ? item.loc : [];
    const field: unknown = loc.at(-1);
    if ((field === 'title' || field === 'description') && typeof item.msg === 'string') {
      fields[field] = item.msg;
    }
  }
  return fields;
}

export function BuilderPage() {
  const { id = '' } = useParams();
  const toast = useToast();
  const mounted = useRef(true);
  const saving = useRef(false);
  const [survey, setSurvey] = useState<Survey | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [accent, setAccent] = useState('');
  const [background, setBackground] = useState('');
  const [previewQuestions, setPreviewQuestions] = useState<Question[]>([]);
  const [loadError, setLoadError] = useState<'not-found' | 'failed' | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [saveError, setSaveError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setSurvey(null);
    setLoadError(null);
    api.survey(id).then(
      (saved) => {
        if (!active) return;
        setSurvey(saved);
        setTitle(saved.title);
        setDescription(saved.description ?? '');
        setAccent(saved.accent_color);
        setBackground(saved.background_color);
      },
      (error) => {
        if (active) setLoadError(error instanceof ApiError && error.status === 404 ? 'not-found' : 'failed');
      },
    );
    return () => { active = false; };
  }, [id, attempt]);

  async function saveDraft(event: FormEvent) {
    event.preventDefault();
    await saveChanges(false);
  }

  /** Saves the form. Returns false when it could not be saved (errors are shown). */
  async function saveChanges(quiet: boolean): Promise<boolean> {
    if (!survey || saving.current) return false;
    const errors = validationErrors(title, description);
    setFieldErrors(errors);
    setSaveError('');
    if (Object.keys(errors).length) return false;

    const changes: Partial<Pick<Survey, 'title' | 'description' | 'accent_color' | 'background_color'>> = {};
    if (title !== survey.title) changes.title = title;
    if (description !== (survey.description ?? '')) changes.description = description;
    if (accent !== survey.accent_color) changes.accent_color = accent;
    if (background !== survey.background_color) changes.background_color = background;
    if (!Object.keys(changes).length) {
      if (!quiet) toast(saveTexts(survey.status).done);
      return true;
    }

    saving.current = true;
    setIsSaving(true);
    try {
      const saved = await api.updateSurvey(id, changes);
      if (!mounted.current) return false;
      setSurvey(saved);
      setTitle(saved.title);
      setDescription(saved.description ?? '');
      setAccent(saved.accent_color);
      setBackground(saved.background_color);
      if (!quiet) toast(saveTexts(survey.status).done);
      return true;
    } catch (error) {
      if (!mounted.current) return false;
      const errorsFromApi = apiErrors(error);
      setFieldErrors(errorsFromApi);
      if (!Object.keys(errorsFromApi).length) {
        setSaveError(saveTexts(survey.status).failed);
      }
      return false;
    } finally {
      saving.current = false;
      if (mounted.current) setIsSaving(false);
    }
  }

  // Thumbs, NPS and CSAT surveys are edited on "Edit and preview", as in the prototype.
  if (survey && survey.type !== 'custom') {
    return <EditPreviewPage key={survey.id} survey={survey} onSaved={setSurvey} />;
  }

  return (
    <>
      <PageHeader
        title="Build your survey"
        description="Write your own questions and pick an answer type for each. Short surveys get more answers."
        actions={survey ? (
          <div className="survey-builder-actions">
            <ButtonLink to="/surveys/new" variant="ghost">Cancel</ButtonLink>
            <Button type="submit" form="survey-details-form" loading={isSaving}>{saveTexts(survey.status).button}</Button>
            <PublishActions survey={survey} onPublish={() => setPublishing(true)} />
          </div>
        ) : undefined}
      />
      <PublishDialog
        survey={publishing && survey ? { id: survey.id, title: title.trim() || survey.title } : null}
        onClose={() => setPublishing(false)}
        beforePublish={() => saveChanges(true)}
      />
      {loadError === 'not-found' ? (
        <div className="survey-error" role="alert">
          <p>Survey not found</p>
          <Link to="/surveys/new">Back to create survey</Link>
        </div>
      ) : loadError === 'failed' ? (
        <div className="survey-error" role="alert">
          <p>We couldn&rsquo;t load this survey. Please try again.</p>
          <Button onClick={() => setAttempt((value) => value + 1)}>Try again</Button>
        </div>
      ) : survey ? (
        <div className="edit-layout">
        <div className="survey-builder">
        <form id="survey-details-form" className="survey-builder-form" onSubmit={saveDraft} noValidate>
          <Card padded className="survey-details-card">
            <TextField
              label="Survey title"
              required
              className="survey-title-input"
              maxLength={SURVEY_TITLE_MAX}
              hint={`Up to ${SURVEY_TITLE_MAX} characters.`}
              value={title}
              error={fieldErrors.title}
              disabled={isSaving}
              onChange={(event) => {
                setTitle(event.target.value);
                setFieldErrors((current) => ({ ...current, title: undefined }));
              }}
            />
            <TextArea
              label="Description (optional)"
              hint={FORMAT_HINT}
              rows={2}
              value={description}
              error={fieldErrors.description}
              disabled={isSaving}
              onChange={(event) => {
                setDescription(event.target.value);
                setFieldErrors((current) => ({ ...current, description: undefined }));
              }}
            />
          </Card>
          {saveError ? <p className="survey-save-error" role="alert">{saveError}</p> : null}
        </form>
        <QuestionList surveyId={survey.id} onQuestionsChange={setPreviewQuestions} />
        <Card padded className="branding-card">
          <Disclosure title={<><strong>Branding</strong> <span className="answer-hint">(optional)</span></>}>
            <BrandingFields
              survey={survey}
              accent={accent}
              background={background}
              onAccentChange={setAccent}
              onBackgroundChange={setBackground}
              onLogoChange={setSurvey}
            />
          </Disclosure>
        </Card>
        </div>
        <CustomPreview
          title={title}
          description={description}
          questions={previewQuestions}
          contactOptIn={survey.contact_opt_in}
          accent={accent}
          background={background}
          logoUrl={survey.logo_url}
        />
        </div>
      ) : <p role="status">Loading your survey&hellip;</p>}
    </>
  );
}
