import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, ApiError, type SurveyListItem, type SurveyStatus, type SurveyType } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import {
  ActionMenu,
  Button,
  ButtonLink,
  Card,
  ConfirmDialog,
  EmptyState,
  SurveyStatusBadge,
  Table,
  SearchInput,
  TextButton,
  ToggleChip,
  icons,
  useToast,
  type Column,
  type MenuAction,
} from '../../components/ui';
import { PublishDialog } from '../publish/PublishDialog';
import { slug } from '../../utils/slug';
import './surveys.css';

// Texts and labels follow the prototype's Surveys screen.
const FILTERS: { label: string; status?: SurveyStatus }[] = [
  { label: 'All' },
  { label: 'Draft', status: 'draft' },
  { label: 'Scheduled', status: 'scheduled' },
  { label: 'Live', status: 'live' },
  { label: 'Closed', status: 'closed' },
];
const STATUSES = new Set<string>(['draft', 'scheduled', 'live', 'closed']);
const TYPE_LABEL: Record<SurveyType, string> = {
  thumbs: 'Thumbs rating',
  nps: 'NPS survey',
  csat: 'CSAT survey',
  custom: 'Custom survey',
};
const UNPUBLISH_ICON = 'M4 12h10M10 6l-6 6 6 6M20 4v16';
const CLOSE_ICON = 'M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4';
const PUBLISH_ICON = 'M12 19V5M5 12l7-7 7 7';
/** Pause after the last key before the list is filtered. */
const SEARCH_DELAY_MS = 250;


/** "Mon 01/12/2026" */
function openDate(iso: string): string {
  const d = new Date(iso);
  const weekday = d.toLocaleDateString('en-GB', { weekday: 'short' });
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${weekday} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
}

function note(survey: SurveyListItem): string {
  if (survey.status === 'live') return `Tag ${slug(survey.title)}`;
  if (survey.status === 'scheduled') return survey.opens_at ? `Opens ${openDate(survey.opens_at)}` : '';
  if (survey.status === 'draft') return 'Not published yet';
  return '';
}

/** Live surveys open their "is live" page (prototype); the rest open the editor. */
function surveyPath(survey: SurveyListItem): string {
  const path = `/surveys/${encodeURIComponent(survey.id)}`;
  return survey.status === 'live' ? `${path}/live` : path;
}

function deleteText(survey: SurveyListItem): string {
  return survey.answers
    ? `The survey and its ${survey.answers} answers will be deleted. This cannot be undone. To keep the results, close the survey instead.`
    : 'The survey will be deleted. This cannot be undone.';
}

export function SurveysPage() {
  const [params, setParams] = useSearchParams();
  const q = (params.get('q') ?? '').trim();
  const statusParam = params.get('status') ?? '';
  const status = STATUSES.has(statusParam) ? (statusParam as SurveyStatus) : undefined;

  const [searchText, setSearchText] = useState(q);
  // Follow the address: "Clear search" and the back button update the box too.
  // Keep what is typed if it only differs by spaces, so a space being typed is not removed.
  useEffect(() => setSearchText((text) => (text.trim() === q ? text : q)), [q]);
  // Filter while typing: a short pause after the last key, at once when the box is emptied.
  // Replaces the address instead of adding to the history on every key.
  useEffect(() => {
    const next = searchText.trim();
    if (next === q) return;
    const timer = setTimeout(
      () =>
        setParams(
          (prev) => {
            const updated = new URLSearchParams(prev);
            if (next) updated.set('q', next);
            else updated.delete('q');
            return updated;
          },
          { replace: true },
        ),
      next ? SEARCH_DELAY_MS : 0,
    );
    return () => clearTimeout(timer);
  }, [searchText, q, setParams]);

  const toast = useToast();
  const navigate = useNavigate();
  const [organisation, setOrganisation] = useState('');
  const [surveys, setSurveys] = useState<SurveyListItem[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [reload, setReload] = useState(0);
  const [deleting, setDeleting] = useState<SurveyListItem | null>(null);
  const [publishing, setPublishing] = useState<SurveyListItem | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    api.me().then(
      (user) => { if (mounted.current) setOrganisation(user.tenant_name); },
      () => {},
    );
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setLoadError(false);
    api.listSurveys({ q: q || undefined, status }).then(
      (rows) => { if (active) setSurveys(rows); },
      () => { if (active) setLoadError(true); },
    );
    return () => { active = false; };
  }, [q, status, reload]);

  function setFilter(changes: { q?: string; status?: string }) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next);
  }

  /** Runs one action at a time, shows a toast, then reloads the list. */
  async function run(action: () => Promise<unknown>, success: string, failure: string) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    try {
      await action();
      if (mounted.current) toast(success);
    } catch (error) {
      // 404: it was already deleted elsewhere; the reload shows that.
      if (mounted.current && !(error instanceof ApiError && error.status === 404)) toast(failure);
    } finally {
      pending.current = false;
      if (mounted.current) {
        setBusy(false);
        setReload((n) => n + 1);
      }
    }
  }

  function actionsFor(survey: SurveyListItem): MenuAction[] {
    const name = `“${survey.title}”`;
    // Live surveys open their "is live" page, so Edit is the way to their editor.
    const items: MenuAction[] = [
      { label: 'Edit', icon: icons.edit, onSelect: () => navigate(`/surveys/${encodeURIComponent(survey.id)}`) },
    ];
    if (survey.answers > 0) {
      items.push({
        label: 'See results',
        icon: icons.chart,
        onSelect: () => navigate(`/results?survey=${encodeURIComponent(survey.id)}`),
      });
    }
    if (survey.status === 'draft') {
      items.push({ label: 'Publish', icon: PUBLISH_ICON, onSelect: () => setPublishing(survey) });
    }
    if (survey.status === 'live' || survey.status === 'scheduled') {
      items.push({
        label: 'Unpublish',
        icon: UNPUBLISH_ICON,
        onSelect: () => void run(
          () => api.changeSurveyStatus(survey.id, 'unpublish'),
          `${name} is unpublished. It is now a draft.`,
          `We couldn’t unpublish ${name}. Please try again.`,
        ),
      });
    }
    if (survey.status === 'live') {
      items.push({
        label: 'Close survey',
        icon: CLOSE_ICON,
        onSelect: () => void run(
          () => api.changeSurveyStatus(survey.id, 'close'),
          `${name} is closed. It no longer takes answers.`,
          `We couldn’t close ${name}. Please try again.`,
        ),
      });
    }
    items.push({ label: 'Delete', icon: icons.trash, danger: true, onSelect: () => setDeleting(survey) });
    return items;
  }

  async function confirmDelete() {
    if (!deleting) return;
    const survey = deleting;
    await run(
      () => api.deleteSurvey(survey.id),
      `“${survey.title}” was deleted.`,
      `We couldn’t delete “${survey.title}”. Please try again.`,
    );
    if (mounted.current) setDeleting(null);
  }

  const columns: Column<SurveyListItem>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (s) => (
        <>
          <Link className="survey-name" title={s.title} to={surveyPath(s)}>{s.title}</Link>
          {note(s) ? <div className="survey-note">{note(s)}</div> : null}
        </>
      ),
    },
    { key: 'type', header: 'Type', render: (s) => TYPE_LABEL[s.type] },
    { key: 'status', header: 'Status', render: (s) => <SurveyStatusBadge status={s.status} /> },
    { key: 'answers', header: 'Answers', numeric: true, render: (s) => s.answers },
    // From the scoring rules (#22), once the survey has answers.
    {
      key: 'score',
      header: 'Headline score',
      render: (s) => (s.headline
        ? <><strong>{s.headline.score}</strong> <span className="survey-note">{s.headline.note}</span></>
        : <strong>—</strong>),
    },
    {
      key: 'actions',
      header: 'Actions',
      hideHeader: true,
      render: (s) => <ActionMenu label={`Actions for ${s.title}`} items={actionsFor(s)} />,
    },
  ];

  let body;
  if (loadError) {
    body = (
      <div className="surveys-error" role="alert">
        <p>We couldn’t load your surveys. Please try again.</p>
        <Button onClick={() => setReload((n) => n + 1)}>Try again</Button>
      </div>
    );
  } else if (surveys === null) {
    body = <p role="status">Loading surveys…</p>;
  } else if (surveys.length === 0 && !q && !status) {
    body = (
      <EmptyState
        icon={icons.list}
        title="No surveys yet."
        actions={<ButtonLink to="/surveys/new" variant="primary" icon={icons.plus}>Create survey</ButtonLink>}
      />
    );
  } else {
    // On a white card with rounded corners, as in the prototype.
    body = (
      <Card className="surveys-table-card">
        <Table
          caption="Surveys"
          columns={columns}
          rows={surveys}
          rowKey={(s) => s.id}
          empty="No surveys match. Try another filter or search."
        />
      </Card>
    );
  }

  return (
    <div className="surveys-page">
      <PageHeader
        title="Surveys"
        description={organisation ? `All surveys for ${organisation}.` : undefined}
      />
      <div className="survey-toolbar">
        <div className="survey-filter-bar">
          <div className="survey-filters" role="group" aria-label="Filter by status">
            {FILTERS.map((f) => (
              <ToggleChip key={f.label} selected={status === f.status} onChange={() => setFilter({ status: f.status })}>
                {f.label}
              </ToggleChip>
            ))}
          </div>
          {/* Searches survey titles, together with the status filter. */}
          <div className="survey-search">
            <SearchInput
              label="Search surveys"
              placeholder="Search by title..."
              value={searchText}
              onChange={setSearchText}
              onSearch={(value) => setFilter({ q: value.trim() || undefined })}
            />
          </div>
        </div>
        <ButtonLink to="/surveys/new" variant="primary" icon={icons.plus}>Create survey</ButtonLink>
      </div>
      {q ? (
        <p className="survey-search-note">
          Showing surveys matching “{q}”.{' '}
          <TextButton onClick={() => setFilter({ q: undefined })}>Clear search</TextButton>
        </p>
      ) : null}
      {body}
      <ConfirmDialog
        open={deleting !== null}
        title={deleting ? `Delete “${deleting.title}”?` : ''}
        confirmLabel="Delete survey"
        danger
        busy={busy}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleting(null)}
      >
        {deleting ? deleteText(deleting) : ''}
      </ConfirmDialog>
      <PublishDialog survey={publishing} onClose={() => setPublishing(null)} />
    </div>
  );
}
