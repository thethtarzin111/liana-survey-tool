import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, type SurveyType, type Template } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Button, Card, SegmentedControl } from '../../components/ui';
import { TYPE_LABEL, templateParts, useStartFromTemplate } from '../templates/templates';
import './builder.css';

const TEMPLATE_TYPES: SurveyType[] = ['thumbs', 'nps', 'csat'];

/** "Pick a template": the wizard step after choosing Thumbs, NPS or CSAT. */
export function TemplatePickerPage() {
  const [params, setParams] = useSearchParams();
  const asked = params.get('type') as SurveyType | null;
  const type: SurveyType = asked && TEMPLATE_TYPES.includes(asked) ? asked : 'thumbs';

  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [pickedId, setPickedId] = useState<string | null>(null);
  const { start, starting, error } = useStartFromTemplate();

  useEffect(() => {
    let active = true;
    setTemplates(null);
    setLoadError(false);
    setPickedId(null);
    api.templates(type).then(
      (list) => { if (active) setTemplates(list); },
      () => { if (active) setLoadError(true); },
    );
    return () => { active = false; };
  }, [type, attempt]);

  const picked = templates?.find((t) => t.id === pickedId) ?? templates?.[0] ?? null;
  const parts = picked ? templateParts(picked) : null;

  return (
    <div className="template-picker">
      <PageHeader title="Pick a template" description="Tested wording, at most 3 questions. You can edit everything next." />
      <SegmentedControl
        label="Survey type"
        options={TEMPLATE_TYPES.map((value) => ({ value, label: TYPE_LABEL[value] }))}
        value={type}
        onChange={(value) => setParams({ type: value })}
      />
      {error ? <p className="survey-error" role="alert">{error}</p> : null}
      {loadError ? (
        <div className="survey-error" role="alert">
          <p>We couldn’t load the templates. Please try again.</p>
          <Button onClick={() => setAttempt((n) => n + 1)}>Try again</Button>
        </div>
      ) : !templates ? (
        <p role="status">Loading templates…</p>
      ) : (
        <Card padded className="template-picker-card">
          <div role="group" aria-label="Templates" className="template-options">
            {templates.map((template) => (
              <button
                key={template.id}
                type="button"
                className="template-option"
                aria-pressed={template.id === picked?.id}
                disabled={starting}
                onClick={() => setPickedId(template.id)}
              >
                <strong>{template.name}</strong>
                <span className="template-hint">{template.description}</span>
              </button>
            ))}
          </div>
          {parts ? (
            <section className="template-contents" aria-label="What the template contains">
              <div className="template-hint">What the template contains</div>
              <div>
                <div className="template-hint">Question</div>
                <strong>{parts.question}</strong>
              </div>
              {parts.reasons.length ? (
                <div>
                  <div className="template-hint">Reasons readers can choose</div>
                  <ul className="template-reasons">
                    {parts.reasons.map((reason) => <li key={reason}>{reason}</li>)}
                  </ul>
                </div>
              ) : null}
              {parts.thanks ? (
                <div>
                  <div className="template-hint">Thank-you message</div>
                  <span>{parts.thanks}</span>
                </div>
              ) : null}
            </section>
          ) : null}
        </Card>
      )}
      <div className="template-picker-footer">
        <Button variant="primary" disabled={!picked} loading={starting} onClick={() => picked && void start(picked)}>
          Continue to edit and preview
        </Button>
        <span className="template-hint">Reason chips and the comment field are set in the next step.</span>
      </div>
    </div>
  );
}
