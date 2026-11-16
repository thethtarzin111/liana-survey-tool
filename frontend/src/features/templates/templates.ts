import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type SurveyType, type Template } from '../../api/client';
import { useToast } from '../../components/ui';

// Labels follow the prototype; "Quick poll" is the badge of the custom Quick poll template.
export const TYPE_LABEL: Record<SurveyType, string> = {
  thumbs: 'Thumbs rating',
  nps: 'NPS survey',
  csat: 'CSAT survey',
  custom: 'Quick poll',
};

export const USE_ERROR = 'We couldn’t create the survey. Please try again.';

/** The parts of a template shown in "What the template contains" and on its card. */
export function templateParts(template: Template) {
  const [main, ...rest] = template.questions;
  return {
    question: main?.prompt ?? '',
    reasons: rest.find((q) => q.kind === 'reasons')?.options ?? [],
    thanks: template.thank_you,
  };
}

/** Creates a draft from a template and opens it. One request at a time. */
export function useStartFromTemplate() {
  const navigate = useNavigate();
  const toast = useToast();
  const pending = useRef(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  async function start(template: Template) {
    if (pending.current) return;
    pending.current = true;
    setStarting(true);
    setError('');
    try {
      const survey = await api.useTemplate(template.id);
      toast('Draft saved');
      navigate(`/surveys/${encodeURIComponent(survey.id)}`);
    } catch {
      setError(USE_ERROR);
      toast(USE_ERROR);
      setStarting(false);
    } finally {
      pending.current = false;
    }
  }

  return { start, starting, error };
}
