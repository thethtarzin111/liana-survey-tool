import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getJson } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import './responses.css';
import { Button, ButtonLink, Card, EmptyState, Table, icons, type Column } from '../../components/ui';

type ResponseRow = { id: string; survey_id: string; survey: string; segment: string; submitted_at: string; answer: number | null; comment: string | null };

export function ResponsesPage() {
  const [rows, setRows] = useState<ResponseRow[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [params, setParams] = useSearchParams();
  const survey = params.get('survey') ?? '';
  const segment = params.get('segment') ?? '';
  useEffect(() => {
    let active = true;
    const load = () => getJson<ResponseRow[]>('/api/v1/results/responses').then(
      (data) => { if (active) { setRows(data); setFailed(false); } },
      () => { if (active) setFailed(true); },
    );
    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [retry]);
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next);
  }
  const columns: Column<ResponseRow>[] = [
    { key: 'answer', header: 'Answer', render: (row) => row.answer ?? '—' },
    { key: 'comment', header: 'Comment', render: (row) => row.comment ?? '—' },
    { key: 'survey', header: 'Survey' },
    { key: 'segment', header: 'Segment' },
    { key: 'submitted_at', header: 'Received', render: (row) => <time dateTime={row.submitted_at}>{new Date(row.submitted_at).toLocaleString()}</time> },
    { key: 'action', header: 'Action', render: (row) => <ButtonLink size="sm" to={`/results?${new URLSearchParams({ survey: row.survey_id, segment: row.segment })}`}>See results</ButtonLink> },
  ];
  const filtered = rows?.filter((row) => (!survey || row.survey_id === survey) && (!segment || row.segment === segment)) ?? [];
  return <div className="responses-page"><PageHeader title="Responses" description="The latest answers and comments across your surveys." />
    {rows?.length ? <div className="result-toolbar">
      <label className="field"><span>Survey</span><select className="input" value={survey} onChange={(e) => filter('survey', e.target.value)}><option value="">All surveys</option>{Array.from(new Map(rows.map((row) => [row.survey_id, row.survey]))).map(([id, title]) => <option key={id} value={id}>{title}</option>)}</select></label>
      <label className="field"><span>Segment</span><select className="input" value={segment} onChange={(e) => filter('segment', e.target.value)}><option value="">All segments</option>{[...new Set(rows.map((row) => row.segment))].sort().map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
    </div> : null}
    {failed ? <Card padded role="alert"><p>We couldn’t load responses.</p><Button onClick={() => setRetry((n) => n + 1)}>Try again</Button></Card> : rows === null ? <p role="status">Loading responses…</p> : !rows.length ? <Card><EmptyState icon={icons.chart} title="No responses yet." text="Share a survey to start collecting answers." /></Card> : <Card><Table caption="Responses" columns={columns} rows={filtered} rowKey={(row) => row.id} empty="No responses match these filters." /></Card>}
  </div>;
}
