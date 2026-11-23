import { useEffect, useMemo, useRef, useState } from 'react';
import { api, ApiError, type Template } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { ActionMenu, Badge, Button, Card, ConfirmDialog, icons, useToast } from '../../components/ui';
import { CreateTemplateDialog } from './CreateTemplateDialog';
import { TemplateDetailsDialog } from './TemplateDetailsDialog';
import { TYPE_LABEL, YOURS, sentence, templateParts, useStartFromTemplate } from './templates';
import './templates.css';

/** The Templates page from the sidebar: a card per featured template, then the organisation's own. */
export function TemplatesPage() {
  const toast = useToast();
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [renaming, setRenaming] = useState<Template | null>(null);
  const renameDetails = useMemo(
    () => renaming && { name: renaming.name, description: renaming.description },
    [renaming],
  );
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Template | null>(null);
  const [deletingBusy, setDeletingBusy] = useState(false);
  const mounted = useRef(true);
  const { start, starting, error } = useStartFromTemplate();

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setLoadError(false);
    api.templates().then(
      (list) => { if (active) setTemplates(list.filter((t) => t.featured || t.own)); },
      () => { if (active) setLoadError(true); },
    );
    return () => { active = false; };
  }, [attempt]);

  async function rename(template: Template, details: { name: string; description: string }) {
    const saved = await api.updateTemplate(template.id, details);
    if (!mounted.current) return;
    setTemplates((list) => list?.map((t) => (t.id === saved.id ? saved : t)) ?? null);
    toast(`Template renamed to “${saved.name}”.`);
  }

  async function confirmDelete() {
    if (!deleting || deletingBusy) return;
    const template = deleting;
    setDeletingBusy(true);
    try {
      await api.deleteTemplate(template.id);
      if (!mounted.current) return;
      toast(`“${template.name}” was deleted.`);
    } catch (e) {
      if (!mounted.current) return;
      // 404: it was already deleted elsewhere; the reload shows that.
      if (!(e instanceof ApiError && e.status === 404)) toast(`We couldn’t delete “${template.name}”. Please try again.`);
    }
    setDeletingBusy(false);
    setDeleting(null);
    setAttempt((n) => n + 1);
  }

  return (
    <>
      <PageHeader
        title="Templates"
        description="Ready-made surveys with tested wording. You can edit everything after you pick one."
        actions={<Button variant="primary" icon={icons.plus} onClick={() => setCreating(true)}>Create template</Button>}
      />
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
                <div className="template-card-badges">
                  <Badge tone="outline">{TYPE_LABEL[template.type]}</Badge>
                  {template.own ? <Badge tone="positive">{YOURS}</Badge> : null}
                  {template.own ? (
                    <ActionMenu
                      label={`Actions for template ${template.name}`}
                      items={[
                        { label: 'Rename', icon: icons.edit, onSelect: () => setRenaming(template) },
                        { label: 'Delete', icon: icons.trash, danger: true, onSelect: () => setDeleting(template) },
                      ]}
                    />
                  ) : null}
                </div>
                <h2>{template.name}</h2>
                {template.description ? <p>{sentence(template.description)}</p> : null}
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
      <CreateTemplateDialog
        open={creating}
        onCreated={(saved) => {
          toast(`“${saved.name}” is saved in Templates.`);
          setAttempt((n) => n + 1);
        }}
        onClose={() => setCreating(false)}
      />
      <TemplateDetailsDialog
        initial={renameDetails}
        title="Rename template"
        confirmLabel="Save"
        failure="We couldn’t rename the template. Please try again."
        onSave={(details) => (renaming ? rename(renaming, details) : Promise.resolve())}
        onClose={() => setRenaming(null)}
      />
      <ConfirmDialog
        open={deleting !== null}
        title={deleting ? `Delete “${deleting.name}”?` : ''}
        confirmLabel="Delete template"
        danger
        busy={deletingBusy}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleting(null)}
      >
        Nobody in your organisation can start from it any more. Surveys made from it stay as they are.
      </ConfirmDialog>
    </>
  );
}
