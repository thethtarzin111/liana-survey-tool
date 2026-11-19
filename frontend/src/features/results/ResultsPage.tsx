import { useCallback, useEffect, useState } from 'react';
import { api, ApiError, type SurveyListItem, type SurveyOverview } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Button, ButtonLink, Card, EmptyState, Select, Tabs, icons } from '../../components/ui';
import { OverviewTab } from './OverviewTab';
import { ResponsesTab, type Scale } from './ResponsesTab';
import { SurveyPicker } from './SurveyPicker';
import { useResultsParams } from './useResultsParams';
import './results.css';

/** The survey in the URL, else the one with the latest answer, else the newest. */
function defaultSurvey(surveys: SurveyListItem[]): SurveyListItem | undefined {
  let latest: SurveyListItem | undefined;
  for (const s of surveys) {
    if (s.last_answer_at && (!latest || s.last_answer_at > (latest.last_answer_at ?? ''))) latest = s;
  }
  return latest ?? surveys[0];
}

/** The survey's first scale question, which the Responses tab filters and shows. */
function scaleOf(overview: SurveyOverview): Scale | null {
  if (overview.type === 'thumbs' || overview.type === 'nps') return overview.type;
  if (overview.type === 'csat') return 'rating';
  const q = overview.questions.find((x) => x.kind === 'nps' || x.kind === 'thumbs' || x.kind === 'rating');
  return q ? (q.kind as Scale) : null;
}

type Loaded = { surveyId: string; segment: string; data: SurveyOverview };

export function ResultsPage() {
  const params = useResultsParams();
  const { survey: urlSurvey, tab, segment, set } = params;
  const [surveys, setSurveys] = useState<SurveyListItem[] | null>(null);
  const [listFailed, setListFailed] = useState(false);
  const [listReload, setListReload] = useState(0);

  useEffect(() => {
    let active = true;
    setListFailed(false);
    api.listSurveys().then(
      (rows) => { if (active) setSurveys(Array.isArray(rows) ? rows : []); },
      () => { if (active) setListFailed(true); },
    );
    return () => { active = false; };
  }, [listReload]);

  const chosen = surveys
    ? urlSurvey
      ? (surveys.find((s) => s.id === urlSurvey) ?? null)
      : (defaultSurvey(surveys) ?? null)
    : null;
  const surveyId = chosen?.id ?? null;

  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [missing, setMissing] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);

  const refused = useCallback(() => set({ segment: 'all' }), [set]);
  useEffect(() => {
    if (!surveyId) return;
    let active = true;
    setFailed(false);
    setMissing(null);
    api.overview(surveyId, segment).then(
      (data) => { if (active) setLoaded({ surveyId, segment, data }); },
      (error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 404) setMissing(surveyId);
        else if (error instanceof ApiError && error.status === 400 && segment !== 'all') refused();
        else setFailed(true);
      },
    );
    return () => { active = false; };
  }, [surveyId, segment, reload, refused]);

  const header = <PageHeader title="Results" description="NPS, CSAT and answer distribution for each survey." />;

  if (listFailed) {
    return (
      <div className="results-page">
        {header}
        <Card padded role="alert" className="results-error">
          <strong>We couldn’t load your surveys.</strong>
          <Button onClick={() => setListReload((n) => n + 1)}>Try again</Button>
        </Card>
      </div>
    );
  }
  if (surveys === null) return <p role="status">Loading results…</p>;
  if (surveys.length === 0) {
    return (
      <div className="results-page">
        {header}
        <Card>
          <EmptyState
            icon={icons.chart}
            title="No surveys yet"
            text="Once a survey is live and people answer, the results show up here."
            actions={<ButtonLink to="/surveys/new" variant="primary" icon={icons.plus}>Create survey</ButtonLink>}
          />
        </Card>
      </div>
    );
  }

  const picker = <SurveyPicker surveys={surveys} value={surveyId} onPick={(id) => set({ survey: id })} />;

  if (!chosen || missing === chosen.id) {
    return (
      <div className="results-page">
        {header}
        <div className="results-top">{picker}</div>
        <Card>
          <EmptyState
            icon={icons.chart}
            title="Survey not found"
            text="It may have been deleted. Choose another survey above."
          />
        </Card>
      </div>
    );
  }

  const overview = loaded && loaded.surveyId === chosen.id ? loaded.data : null;
  let body;
  if (failed) {
    body = (
      <Card padded role="alert" className="results-error">
        <strong>We couldn’t load these results.</strong>
        <Button onClick={() => setReload((n) => n + 1)}>Try again</Button>
      </Card>
    );
  } else if (!overview) {
    body = <p role="status">Loading results…</p>;
  } else {
    const showSegments = overview.segments.length >= 2;
    body = (
      <Tabs
        className="results-tabs"
        label="Results views"
        value={tab}
        actions={
          showSegments ? (
            <div className="results-segment">
              <Select
                label="Segment"
                value={segment}
                onChange={(e) => set({ segment: e.target.value })}
                options={[
                  { value: 'all', label: 'All segments' },
                  ...overview.segments.map((s) => ({ value: s.value, label: `${s.label} (${s.answers})` })),
                ]}
              />
            </div>
          ) : undefined
        }
        onChange={(id) => set({ tab: id === 'responses' ? 'responses' : 'overview' })}
        tabs={[
          { id: 'overview', label: 'Overview' },
          {
            id: 'responses',
            label: (
              <>
                Responses <span className="results-count">{overview.responses}</span>
              </>
            ),
          },
        ]}
      >
        {tab === 'responses' ? (
          <ResponsesTab surveyId={chosen.id} segment={segment} scale={scaleOf(overview)} />
        ) : (
          <OverviewTab overview={overview} onReadAll={() => set({ tab: 'responses' })} />
        )}
      </Tabs>
    );
  }

  return (
    <div className="results-page">
      {header}
      <div className="results-top">{picker}</div>
      {body}
    </div>
  );
}
