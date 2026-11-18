import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, errorDetail, type Survey } from '../../api/client';
import { Button, ButtonLink, ConfirmDialog, useToast } from '../../components/ui';
import './publish.css';

const PUBLISH_ERROR = 'We couldn’t publish the survey. Please try again.';

type Props = {
  /** The draft to publish; the dialog is open while this is set. */
  survey: { id: string; title: string } | null;
  onClose: () => void;
  /** Runs first, e.g. to save unsaved changes. Return false to stop. */
  beforePublish?: () => Promise<boolean>;
};

/** "Publish …?" Then the survey goes live and the "… is live" page opens (#117). */
export function PublishDialog({ survey, onClose, beforePublish }: Props) {
  const navigate = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => setError(''), [survey]);

  async function publish() {
    if (!survey || busy) return;
    setBusy(true);
    setError('');
    try {
      if (beforePublish && !(await beforePublish())) {
        if (mounted.current) onClose();
        return;
      }
      await api.publishSurvey(survey.id);
      if (!mounted.current) return;
      toast(`“${survey.title}” is live.`);
      onClose();
      navigate(`/surveys/${encodeURIComponent(survey.id)}/live`);
    } catch (e) {
      // 409: not ready yet, e.g. "Add the survey's main question before publishing."
      if (mounted.current) setError(errorDetail(e) ?? PUBLISH_ERROR);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  return (
    <ConfirmDialog
      open={survey !== null}
      title={survey ? `Publish “${survey.title}”?` : ''}
      confirmLabel="Publish"
      busy={busy}
      onConfirm={() => void publish()}
      onCancel={onClose}
    >
      <p>The survey goes live and its link starts taking answers. You can unpublish it later.</p>
      {error ? <p className="publish-error" role="alert">{error}</p> : null}
    </ConfirmDialog>
  );
}

/** Edit pages: Publish for drafts, Share for live surveys. */
export function PublishActions({ survey, onPublish }: { survey: Survey; onPublish: () => void }) {
  if (survey.status === 'draft') return <Button variant="primary" onClick={onPublish}>Publish</Button>;
  if (survey.status === 'live') {
    return <ButtonLink to={`/surveys/${encodeURIComponent(survey.id)}/live`} variant="secondary">Share</ButtonLink>;
  }
  return null;
}
