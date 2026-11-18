import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, type SurveyListItem, type SurveyResult } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Button, Card, EmptyState, LiveIndicator, Tabs, icons } from '../../components/ui';
import './results.css';

const LABELS: Record<string, Record<number, string>> = {
  thumbs: { 0: 'Not for me', 1: 'Good', 2: 'Loved it' },
  nps: { 0: '0', 1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9', 10: '10' },
  csat: { 1: 'Very dissatisfied', 2: 'Dissatisfied', 3: 'Neutral', 4: 'Satisfied', 5: 'Very satisfied' },
};

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
  const [view, setView] = useState('summary');
  const selected = params.get('survey') ?? surveys?.[0]?.id ?? '';
  const segment = params.get('segment') ?? 'all';

  useEffect(() => { api.listSurveys().then(setSurveys, () => setFailed(true)); }, []);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setResult(null);
    setFailed(false);
    api.result(selected, segment).then((data) => { if (active) setResult(data); }, () => { if (active) setFailed(true); });
    const timer = window.setInterval(() => {
      api.result(selected, segment).then((data) => { if (active) setResult(data); }, () => {});
    }, 30_000);
    return () => { active = false; window.clearInterval(timer); };
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
    <Tabs label="Result views" tabs={[{id:'summary',label:'In short'},{id:'reasons',label:'Reasons'},{id:'comments',label:'Comments'}]} value={view} onChange={setView}>
    {view === 'comments' ? <Card padded><h2>Latest comments</h2>{result.comments?.length ? <ul className="list">{result.comments.map((comment) => <li className="list-item" key={comment.id}><blockquote>{comment.comment}</blockquote><span>Answer: {comment.answer === null ? '—' : LABELS[result.type]?.[comment.answer] ?? comment.answer} · Segment: {comment.segment}</span><time dateTime={comment.submitted_at}>{new Date(comment.submitted_at).toLocaleString()}</time></li>)}</ul> : <p>No comments yet.</p>}</Card>
      : view === 'reasons' ? <Card padded><h2>Top reasons</h2>{result.questions?.some((q) => q.kind === 'reasons' && q.answers > 0) ? result.questions.filter((q) => q.kind === 'reasons').map((question) => <section key={question.id}><h3>{question.prompt || 'Why people answered this way'}</h3><p>{question.answers} respondents in {segment === 'all' ? 'all segments' : segment}</p><ol>{[...question.options].sort((a,b) => b.count-a.count || a.label.localeCompare(b.label)).map((option) => <li key={option.label}>{option.label}: <strong>{option.count}</strong></li>)}</ol></section>) : <p>No reasons yet.</p>}</Card> : <>
    <section role="tabpanel" className="result-summary">
      {result.questions?.map((question) => <Card padded key={question.id}>
        <h2>{question.prompt}</h2>
        <p>{question.answers} answers · Percentages of respondents answering this question</p>
        {question.options.map((option) => <div key={option.label}>
          <strong>{option.label}</strong> — {option.count} answers ({question.answers ? Math.round(option.count / question.answers * 100) : 0}%)
          <div className="progress" aria-hidden="true"><div className="progress-fill" style={{ width: `${question.answers ? option.count / question.answers * 100 : 0}%` }} /></div>
        </div>)}
      </Card>)}
      <div className="result-metrics">
        <Card padded><span>Headline score</span><strong>{result.headline?.score}</strong><small>{result.headline?.note}</small></Card>
        <Card padded><span>Answers</span><strong>{result.answers}</strong><small>{segment === 'all' ? 'All segments' : `Segment: ${segment}`}</small></Card>
      </div>
      <Card padded className="answer-split"><h2>Answer split</h2><div className="split-bar" role="img" aria-label={result.split.map((item) => `${LABELS[result.type]?.[item.value] ?? item.value}: ${item.percent ?? 0}%`).join(', ')}>{result.split.filter((item) => item.count > 0).map((item) => <span key={item.value} style={{ width: `${item.percent}%` }}>{item.percent}%</span>)}</div><ul>{result.split.map((item) => <li key={item.value}><i aria-hidden="true" /><strong>{LABELS[result.type]?.[item.value] ?? item.value}</strong><span>{item.percent ?? 0}% · {item.count} answers</span></li>)}</ul></Card>
    </section>
    </>}
    </Tabs>
  </>;

  return <div className="results-page"><PageHeader title="Results" description={result?.title ?? 'See how each survey performed.'} />{surveys?.length ? <div className="result-surveys" role="group" aria-label="Survey">{surveys.map((survey) => <button key={survey.id} type="button" className="chip" aria-pressed={survey.id === selected} onClick={() => choose({ survey: survey.id })}>{survey.title}</button>)}</div> : null}{content}</div>;
}
