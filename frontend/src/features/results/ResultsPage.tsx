import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, type SurveyListItem, type SurveyResult } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Button, Card, EmptyState, LiveIndicator, icons } from '../../components/ui';
import './results.css';
import { ResultSummary } from './ResultSummary';


function takeaway(result: SurveyResult) {
  if (!result.headline) return 'Answers will be summarised here as soon as they arrive.';
  return `${result.headline.score} from ${result.answers} ${result.answers === 1 ? 'answer' : 'answers'}${result.segment === 'all' ? '.' : ` in the ${result.segment} segment.`}`;
}

export function ResultsPage() {
  const [params, setParams] = useSearchParams();
  const [surveys, setSurveys] = useState<SurveyListItem[] | null>(null);
  const [result, setResult] = useState<SurveyResult | null>(null);
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);
  const selected = params.get('survey') ?? surveys?.[0]?.id ?? '';
  const segment = params.get('segment') ?? 'all';

  useEffect(() => { api.listSurveys().then(setSurveys, () => setFailed(true)); }, []);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setResult(null);
    setFailed(false);
    api.result(selected, segment).then((data) => { if (active) setResult(data); }, () => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [selected, segment, reload]);

  function choose(changes: { survey?: string; segment?: string }) {
    const next = new URLSearchParams(params);
    if (changes.survey) { next.set('survey', changes.survey); next.delete('segment'); }
    if (changes.segment) {
      if (changes.segment === 'all') next.delete('segment');
      else next.set('segment', changes.segment);
    }
    setParams(next);
  }

  let content;
  if (failed) content = <Card padded role="alert"><p>We couldn’t load these results.</p><Button onClick={() => setReload((n) => n + 1)}>Try again</Button></Card>;
  else if (surveys === null || (selected && result === null)) content = <p role="status">Loading results…</p>;
  else if (!surveys.length) content = <Card><EmptyState icon={icons.chart} title="No surveys yet." text="Create and publish a survey to collect results." /></Card>;
  else if (!result || result.answers === 0) content = <Card><EmptyState icon={icons.chart} title="No answers yet." text="Share this survey and its results will appear here." /></Card>;
  else content = <>
    <Card padded className="result-takeaway"><span>In short</span><p>{takeaway(result)}</p></Card>
    <div className="result-toolbar">
      <label className="field"><span className="field-label">Segment</span><select className="input" value={segment} onChange={(e) => choose({ segment: e.target.value })}><option value="all">All segments</option>{result.segments.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      <LiveIndicator>Live · updated just now</LiveIndicator>
    </div>
    <div className="tabs" role="tablist" aria-label="Result views"><button className="tab" role="tab" aria-selected="true">In short</button></div>
    <section role="tabpanel" className="result-summary">
      <ResultSummary result={result} />
    </section>
  </>;

  return <div className="results-page"><PageHeader title="Results" description={result?.title ?? 'See how each survey performed.'} />{surveys?.length ? <div className="result-surveys" role="group" aria-label="Survey">{surveys.map((survey) => <button key={survey.id} type="button" className="chip" aria-pressed={survey.id === selected} onClick={() => choose({ survey: survey.id })}>{survey.title}</button>)}</div> : null}{content}</div>;
}
