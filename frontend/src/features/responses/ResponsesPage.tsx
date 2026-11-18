import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, getJson } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Button, ButtonLink, Card, EmptyState, Table, icons, type Column } from '../../components/ui';

type ResponseRow = { id: string; survey_id: string; survey: string; segment: string; submitted_at: string; answer: number | null; comment: string | null };

export function ResponsesPage() {
  const [rows, setRows] = useState<ResponseRow[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [surveys, setSurveys] = useState<{id: string; title: string}[]>([]);
  const [segments, setSegments] = useState<string[]>([]);
  const [hasNext, setHasNext] = useState(false);
  const [params, setParams] = useSearchParams();
  const survey = params.get('survey') ?? '';
  const segment = params.get('segment') ?? '';
  const pageValue = Number(params.get('page') ?? '0');
  const page = Number.isSafeInteger(pageValue) && pageValue >= 0 ? pageValue : 0;
  useEffect(() => { api.listSurveys().then(setSurveys, () => {}); }, []);
  useEffect(() => {
    let active = true;
    setRows(null);
    setFailed(false);
    const query = new URLSearchParams({ limit: '51', offset: String(page * 50) });
    if (survey) query.set('survey_id', survey);
    if (segment) query.set('segment', segment);
    const load = () => getJson<ResponseRow[]>(`/api/v1/results/responses?${query}`).then(
      (data) => { if (active) {
        setRows(data.slice(0, 50)); setHasNext(data.length > 50); setFailed(false);
        setSegments((previous) => [...new Set([...previous, ...data.map((row) => row.segment)])].sort());
      } },
      () => { if (active) setFailed(true); },
    );
    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [retry, survey, segment, page]);
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    if (key !== 'page') next.delete('page');
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
  return <><PageHeader title="Responses" description="The latest answers and comments across your surveys." />
    <div className="result-toolbar">
      <label className="field"><span>Survey</span><select className="input" value={survey} onChange={(e) => filter('survey', e.target.value)}><option value="">All surveys</option>{surveys.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
      <label className="field"><span>Segment</span><input className="input" list="response-segments" value={segment} placeholder="All segments" onChange={(e) => filter('segment', e.target.value)} /><datalist id="response-segments">{segments.map((item) => <option key={item} value={item} />)}</datalist></label>
      <Button onClick={() => setParams({})}>Clear filters</Button>
    </div>
    {failed ? <Card padded role="alert"><p>We couldn’t load responses.</p><Button onClick={() => setRetry((n) => n + 1)}>Try again</Button></Card> : rows === null ? <p role="status">Loading responses…</p> : !rows.length ? <Card><EmptyState icon={icons.chart} title="No responses yet." text="Share a survey to start collecting answers." /></Card> : <Card><Table caption="Responses" columns={columns} rows={filtered} rowKey={(row) => row.id} empty="No responses match these filters." /></Card>}
    {rows !== null && !failed ? <nav aria-label="Response pages"><Button disabled={page === 0} onClick={() => filter('page', String(page - 1))}>Previous</Button><span> Page {page + 1} </span><Button disabled={!hasNext} onClick={() => filter('page', String(page + 1))}>Next</Button></nav> : null}
  </>;
}
