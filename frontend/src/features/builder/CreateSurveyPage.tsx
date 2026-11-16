import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type SurveyType } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Button, OptionCard, useToast } from '../../components/ui';
import { surveyTypes } from './surveyTypes';
import './builder.css';

const SAVE_ERROR = 'We couldn’t save your draft. Please try again.';

export function CreateSurveyPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const pending = useRef(false);
  const active = useRef(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    active.current = true;
    return () => { active.current = false; };
  }, []);

  async function choose(type: SurveyType) {
    // Guard the request immediately, before React renders disabled cards.
    if (pending.current) return;
    // Thumbs, NPS and CSAT start from a template; the draft is created there.
    if (type !== 'custom') {
      navigate(`/surveys/new/template?${new URLSearchParams({ type })}`);
      return;
    }
    pending.current = true;
    setSaving(true);
    setError('');
    try {
      const survey = await api.createSurvey(type);
      if (!active.current) return;
      toast('Draft saved');
      navigate(`/surveys/${encodeURIComponent(survey.id)}`);
    } catch {
      if (!active.current) return;
      setError(SAVE_ERROR);
      toast(SAVE_ERROR);
    } finally {
      pending.current = false;
      if (active.current) setSaving(false);
    }
  }

  return (
    <div className="survey-create">
      <PageHeader
        title="What do you want to find out?"
        description="Pick a type. The scales are standard, so results stay comparable over time."
      />
      {error ? <p className="survey-error" role="alert">{error}</p> : null}
      <section className="survey-types" aria-label="Survey types" aria-busy={saving}>
        {surveyTypes.map((option) => (
          <OptionCard
            key={option.type}
            title={option.title}
            icon={option.icon}
            description={<><strong>Use this when</strong> {option.useWhen}</>}
            disabled={saving}
            onClick={() => void choose(option.type)}
          >
            <span className="survey-type-detail">{option.detail}</span>
            <span className="survey-type-action">{option.action} <span aria-hidden="true">→</span></span>
          </OptionCard>
        ))}
      </section>
      <div className="survey-create-footer">
        <Button disabled={saving} onClick={() => navigate('/surveys')}>Cancel</Button>
        {saving ? <span role="status">Saving your draft…</span> : <span>Start from scratch saves a new draft right away.</span>}
      </div>
    </div>
  );
}
