import { useEffect, useRef, useState } from 'react';
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

/** A description as a sentence: adds a full stop unless it already ends with one. */
export function sentence(text: string): string {
  return /[.!?]$/.test(text.trim()) ? text.trim() : `${text.trim()}.`;
}

/** Creates a draft from a template and opens it. One request at a time.
 *  If the user leaves the page meanwhile, the draft is still saved but they stay where they went. */
export function useStartFromTemplate() {
  const navigate = useNavigate();
  const toast = useToast();
  const pending = useRef(false);
  const mounted = useRef(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  async function start(template: Template) {
    if (pending.current) return;
    pending.current = true;
    setStarting(true);
    setError('');
    try {
      const survey = await api.useTemplate(template.id);
      if (!mounted.current) return;
      toast('Draft saved');
      navigate(`/surveys/${encodeURIComponent(survey.id)}`);
    } catch {
      if (!mounted.current) return;
      setError(USE_ERROR);
      toast(USE_ERROR);
      setStarting(false);
    } finally {
      pending.current = false;
    }
  }

  return { start, starting, error };
}
