import { useEffect, useState } from 'react';
import { getJson, type SurveyResult } from '../../api/client';
import { Button, Card, EmptyState, icons } from '../../components/ui';

type Reason = NonNullable<SurveyResult['questions']>[number];
type Comment = NonNullable<SurveyResult['comments']>[number];

export function ResultDetails({ surveyId, segment, view }: {
  surveyId: string; segment: string; view: 'reasons' | 'comments';
}) {
  const [data, setData] = useState<(Reason | Comment)[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setFailed(false);
    const load = () => getJson<(Reason | Comment)[]>(`/api/v1/results/${encodeURIComponent(surveyId)}/${view}?${new URLSearchParams({ segment })}`).then(
      (rows) => { if (active) { setData(rows); setFailed(false); } },
      () => { if (active) setFailed(true); },
    );
    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [surveyId, segment, view, retry]);

  if (failed) return <Card padded role="alert"><p>We couldn’t load {view}.</p><Button onClick={() => setRetry((n) => n + 1)}>Try again</Button></Card>;
  if (data === null) return <p role="status">Loading {view}…</p>;
  if (!data.length || (view === 'reasons' && !(data as Reason[]).some((q) => q.options.some((option) => option.count > 0)))) {
    return <Card><EmptyState icon={icons.chart} title={view === 'reasons' ? 'No reasons yet.' : 'No comments yet.'} text={segment === 'all' ? 'Responses will appear here when readers share their feedback.' : `No ${view} for the ${segment} segment. Choose All segments to see more feedback.`} /></Card>;
  }
  return <Card padded>{view === 'comments' ? <><h2>Latest comments</h2><ul className="list">{(data as Comment[]).map((comment) => <li className="list-item" key={comment.id}><blockquote>{comment.comment}</blockquote><span>Answer: {comment.answer ?? '—'} · Segment: {comment.segment}</span><time dateTime={comment.submitted_at}>{new Date(comment.submitted_at).toLocaleString()}</time></li>)}</ul></> : <><h2>Top reasons</h2>{(data as Reason[]).map((question) => <section key={question.id}><h3>{question.prompt || 'Why people answered this way'}</h3><p>{question.answers} respondents · {segment === 'all' ? 'All segments' : segment}</p><ol>{question.options.map((option) => <li key={option.label}>{option.label}: <strong>{option.count}</strong></li>)}</ol></section>)}</>}</Card>;
}
