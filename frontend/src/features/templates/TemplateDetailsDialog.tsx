import { useEffect, useRef, useState, type ReactNode } from 'react';
import { errorDetail, type TemplateDetails } from '../../api/client';
import { ConfirmDialog, TextArea, TextField } from '../../components/ui';
import './templates.css';

/** Longest template name, as for survey titles in the API. */
export const NAME_MAX = 80;
export const DESCRIPTION_MAX = 1000;

type TemplateDetailsDialogProps = {
  /** Shows the dialog with these values; null closes it. */
  initial: TemplateDetails | null;
  title: string;
  confirmLabel: string;
  intro?: ReactNode;
  /** Saves the details. Errors are shown in the dialog. */
  onSave: (details: TemplateDetails) => Promise<void>;
  /** The message when saving fails without a reason from the API. */
  failure: string;
  onClose: () => void;
};

/** A template's name and description, for "Save as template" and "Rename". */
export function TemplateDetailsDialog({ initial, title, confirmLabel, intro, onSave, failure, onClose }: TemplateDetailsDialogProps) {
  const [name, setName] = useState('');
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
    if (!initial) return;
    setName(initial.name);
    setDescription(initial.description);
    setNameError('');
    setSaveError('');
  }, [initial]);

  async function save() {
    if (busy) return;
    const trimmed = name.trim();
    if (!trimmed) return setNameError('Give the template a name');
    if (trimmed.length > NAME_MAX) return setNameError(`Name must be ${NAME_MAX} characters or fewer`);
    setNameError('');
    setSaveError('');
    setBusy(true);
    try {
      await onSave({ name: trimmed, description: description.trim() });
      if (mounted.current) onClose();
    } catch (error) {
      if (mounted.current) setSaveError(errorDetail(error) ?? failure);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  return (
    <ConfirmDialog
      open={initial !== null}
      title={title}
      confirmLabel={confirmLabel}
      busy={busy}
      onConfirm={() => void save()}
      onCancel={onClose}
    >
      <div className="template-details">
        {intro ? <p>{intro}</p> : null}
        <TextField
          label="Template name"
          required
          value={name}
          error={nameError}
          disabled={busy}
          onChange={(e) => setName(e.target.value)}
        />
        <TextArea
          label="Description"
          hint="Shown with the template, e.g. who it is for."
          value={description}
          maxLength={DESCRIPTION_MAX}
          disabled={busy}
          onChange={(e) => setDescription(e.target.value)}
        />
        {saveError ? <p className="templates-error" role="alert">{saveError}</p> : null}
      </div>
    </ConfirmDialog>
  );
}
