import { useEffect, useState } from 'react';
import { api, type Template } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Badge, Button, Card } from '../../components/ui';
import { TYPE_LABEL, templateParts, useStartFromTemplate } from './templates';
import './templates.css';

/** The Templates page from the sidebar: one card per featured template. */
export function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const { start, starting, error } = useStartFromTemplate();

  useEffect(() => {
    let active = true;
    setLoadError(false);
    api.templates().then(
      (list) => { if (active) setTemplates(list.filter((t) => t.featured)); },
      () => { if (active) setLoadError(true); },
    );
    return () => { active = false; };
  }, [attempt]);

  return (
    <>
      <PageHeader title="Templates" description="Ready-made surveys with tested wording. You can edit everything after you pick one." />
      {error ? <p className="templates-error" role="alert">{error}</p> : null}
      {loadError ? (
        <div className="templates-error" role="alert">
          <p>We couldn’t load the templates. Please try again.</p>
          <Button onClick={() => setAttempt((n) => n + 1)}>Try again</Button>
        </div>
      ) : !templates ? (
        <p role="status">Loading templates…</p>
      ) : (
        <ul className="template-cards" aria-label="Templates">
          {templates.map((template) => (
            <li key={template.id}>
              <Card padded className="template-card">
                <Badge tone="outline">{TYPE_LABEL[template.type]}</Badge>
                <h2>{template.name}</h2>
                <p>{template.description}.</p>
                <p><strong>Question:</strong> {templateParts(template).question}</p>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={starting}
                  aria-label={`Use template ${template.name}`}
                  onClick={() => void start(template)}
                >
                  Use template
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
