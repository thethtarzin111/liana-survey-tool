import { useMemo, useRef, useState } from 'react';
import { api } from '../../api/client';
import { Button, useToast } from '../../components/ui';
import { NAME_MAX, TemplateDetailsDialog } from './TemplateDetailsDialog';

type SaveAsTemplateButtonProps = {
  surveyId: string;
  /** The survey's current name: the dialog's title and the suggested template name. */
  title: string;
  /** Saves the editor's form first. Returns false when it could not be saved (the editor shows why). */
  beforeSave: () => Promise<boolean>;
};

/** "Save as template" in the survey editors: saves the draft, then asks for the template's name and description. */
export function SaveAsTemplateButton({ surveyId, title, beforeSave }: SaveAsTemplateButtonProps) {
  const toast = useToast();
  const [preparing, setPreparing] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const pending = useRef(false);
  const details = useMemo(() => saving !== null && { name: saving.slice(0, NAME_MAX), description: '' }, [saving]);

  async function open() {
    if (pending.current) return;
    pending.current = true;
    setPreparing(true);
    try {
      if (await beforeSave()) setSaving(title);
    } finally {
      pending.current = false;
      setPreparing(false);
    }
  }

  return (
    <>
      <Button loading={preparing} onClick={() => void open()}>Save as template</Button>
      <TemplateDetailsDialog
        initial={details || null}
        title={saving !== null ? `Save “${saving}” as a template` : ''}
        intro="Your organisation can start new surveys from it. It keeps the questions and the thank-you message."
        confirmLabel="Save template"
        failure="We couldn’t save the template. Please try again."
        onSave={async (values) => {
          const saved = await api.saveAsTemplate(surveyId, values);
          toast(`“${saved.name}” is saved in Templates.`);
        }}
        onClose={() => setSaving(null)}
      />
    </>
  );
}
