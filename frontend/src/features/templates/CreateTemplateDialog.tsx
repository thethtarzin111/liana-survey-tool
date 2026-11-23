import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, errorDetail, type SurveyListItem, type Template } from '../../api/client';
import { Button, ConfirmDialog, Select, TextArea, TextField } from '../../components/ui';
import { DESCRIPTION_MAX, NAME_MAX } from './TemplateDetailsDialog';
import { TYPE_LABEL } from './templates';
import './templates.css';

const FAILURE = 'We couldn’t save the template. Please try again.';

type CreateTemplateDialogProps = {
  open: boolean;
  /** Called with the new template after it is saved. */
  onCreated: (template: Template) => void;
  onClose: () => void;
};

/** "Create template" on the Templates page: pick one of the organisation's surveys, then name the template. */
export function CreateTemplateDialog({ open, onCreated, onClose }: CreateTemplateDialogProps) {
  const navigate = useNavigate();
  const [surveys, setSurveys] = useState<SurveyListItem[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [surveyId, setSurveyId] = useState('');
  const [name, setName] = useState('');
  const [nameEdited, setNameEdited] = useState(false);
  const [description, setDescription] = useState('');
  const [nameError, setNameError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setSurveys(null);
    setLoadError(false);
    setName('');
    setNameEdited(false);
    setDescription('');
    setNameError('');
    setSaveError('');
    api.listSurveys().then(
      (list) => {
        if (!active) return;
        setSurveys(list);
        setSurveyId(list[0]?.id ?? '');
        setName((list[0]?.title ?? '').slice(0, NAME_MAX));
      },
      () => { if (active) setLoadError(true); },
    );
    return () => { active = false; };
  }, [open, attempt]);

  function chooseSurvey(id: string) {
    setSurveyId(id);
    setSaveError('');
    // Follow the chosen survey's name until the user types their own.
    if (!nameEdited) setName((surveys?.find((s) => s.id === id)?.title ?? '').slice(0, NAME_MAX));
  }

  async function save() {
    if (busy) return;
    if (surveys && !surveys.length) {
      onClose();
      navigate('/surveys/new');
      return;
    }
    if (!surveyId) return;
    const trimmed = name.trim();
    if (!trimmed) return setNameError('Give the template a name');
    if (trimmed.length > NAME_MAX) return setNameError(`Name must be ${NAME_MAX} characters or fewer`);
    setNameError('');
    setSaveError('');
    setBusy(true);
    try {
      const saved = await api.saveAsTemplate(surveyId, { name: trimmed, description: description.trim() });
      if (!mounted.current) return;
      onCreated(saved);
      onClose();
    } catch (error) {
      if (mounted.current) setSaveError(errorDetail(error) ?? FAILURE);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  const empty = surveys !== null && surveys.length === 0;

  return (
    <ConfirmDialog
      open={open}
      title="Create template"
      confirmLabel={empty ? 'Create survey' : 'Save template'}
      busy={busy}
      onConfirm={() => void save()}
      onCancel={onClose}
    >
      <div className="template-details">
        {loadError ? (
          <div className="templates-error" role="alert">
            <p>We couldn’t load your surveys. Please try again.</p>
            <Button size="sm" onClick={() => setAttempt((n) => n + 1)}>Try again</Button>
          </div>
        ) : surveys === null ? (
          <p role="status">Loading your surveys…</p>
        ) : empty ? (
          <p>A template starts from one of your surveys. Create a survey first, then save it as a template.</p>
        ) : (
          <>
            <p>A template copies a survey’s questions and thank-you message. Your organisation can start new surveys from it.</p>
            <Select
              label="Survey"
              value={surveyId}
              disabled={busy}
              options={surveys.map((s) => ({ value: s.id, label: `${s.title} (${TYPE_LABEL[s.type]})` }))}
              onChange={(e) => chooseSurvey(e.target.value)}
            />
            <TextField
              label="Template name"
              required
              value={name}
              error={nameError}
              disabled={busy}
              onChange={(e) => { setName(e.target.value); setNameEdited(true); }}
            />
            <TextArea
              label="Description"
              hint="Shown with the template, e.g. who it is for."
              value={description}
              maxLength={DESCRIPTION_MAX}
              disabled={busy}
              onChange={(e) => setDescription(e.target.value)}
            />
          </>
        )}
        {saveError ? <p className="templates-error" role="alert">{saveError}</p> : null}
      </div>
    </ConfirmDialog>
  );
}
