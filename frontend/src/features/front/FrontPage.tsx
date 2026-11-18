import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useCurrentUser } from '../../api/useCurrentUser';
import { api, type SurveyListItem, type SurveyType } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Button, ButtonLink, Card, CardBody, CardHeader, EmptyState, SurveyStatusBadge, Table, icons, type Column } from '../../components/ui';
import './front.css';

const TYPE_LABEL: Record<SurveyType, string> = { thumbs: 'Thumbs rating', nps: 'NPS survey', csat: 'CSAT survey', custom: 'Custom survey' };
const NEWS = [
  ['Introducing LianaSurvey: surveys that work with your other Liana tools', '14 Nov 2026'],
  ['New: share surveys with a QR code or embed them on your website', '10 Nov 2026'],
  ['Survey templates now in Finnish, Swedish and English', '4 Nov 2026'],
] as const;
const INSPIRATION = [
  ['How to write a good NPS question', '12 Nov 2026'],
  ['Close the loop: reply to every “Not for me”', '29 Oct 2026'],
  ['Short surveys get more answers: keep it to three questions', '16 Oct 2026'],
] as const;

function surveyPath(survey: SurveyListItem) {
  const path = `/surveys/${encodeURIComponent(survey.id)}`;
  return survey.status === 'live' ? `${path}/live` : path;
}

function GettingStarted() {
  return <Card className="front-getting-started" aria-labelledby="getting-started-title">
    <CardHeader id="getting-started-title" title="Get started with LianaSurvey" />
    <CardBody>
      <p>Create your first survey and start hearing what your readers think.</p>
      <ol className="front-steps">
        <li><span>1</span><div><strong>Create a survey</strong><small>Start from scratch or choose a ready-made template.</small></div></li>
        <li><span>2</span><div><strong>Publish and share it</strong><small>Send it by email, link, or QR code.</small></div></li>
        <li><span>3</span><div><strong>Follow the results</strong><small>See responses and contact requests in one place.</small></div></li>
      </ol>
      <div className="front-actions"><ButtonLink to="/surveys/new" variant="primary" icon={icons.plus}>Create survey</ButtonLink><ButtonLink to="/templates">Browse templates</ButtonLink></div>
    </CardBody>
  </Card>;
}

function ArticleList({ items }: { items: readonly (readonly [string, string])[] }) {
  return <ul className="front-links">{items.map(([title, date]) => <li key={title}><a href="https://www.lianatech.com/resources/blog/" target="_blank" rel="noreferrer">{title} ↗</a><small>{date}</small></li>)}</ul>;
}

export function FrontPage() {
  const user = useCurrentUser();
  const [surveys, setSurveys] = useState<SurveyListItem[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    api.listSurveys().then((rows) => { if (active) setSurveys(Array.isArray(rows) ? rows : []); }, () => { if (active) setFailed(true); });
    return () => { active = false; };
  }, []);

  const recent = surveys?.slice(0, 4) ?? [];
  const live = surveys?.filter((survey) => survey.status === 'live').length ?? 0;
  const responses = surveys?.reduce((sum, survey) => sum + survey.answers, 0) ?? 0;
  const withResults = surveys?.filter((survey) => survey.answers > 0).slice(0, 3) ?? [];
  const columns: Column<SurveyListItem>[] = [
    { key: 'title', header: 'Survey', render: (survey) => <div><Link className="front-survey-link" to={surveyPath(survey)}>{survey.title}</Link><small>{TYPE_LABEL[survey.type]}</small></div> },
    { key: 'status', header: 'Status', render: (survey) => <SurveyStatusBadge status={survey.status} /> },
    { key: 'answers', header: 'Responses', numeric: true },
    { key: 'open', header: 'Action', hideHeader: true, render: (survey) => <ButtonLink size="sm" to={surveyPath(survey)}>Open</ButtonLink> },
  ];

  return <div className="front-page">
    <PageHeader title={user ? `Welcome, ${user.name.split(' ')[0]}` : 'Welcome'} description="Your surveys and the latest results at a glance." actions={<ButtonLink to="/surveys/new" variant="primary" icon={icons.plus}>Create survey</ButtonLink>} />
    {failed ? <Card padded className="front-error" role="alert"><strong>We couldn’t load your dashboard.</strong><p>Your survey information is temporarily unavailable.</p><Button onClick={() => window.location.reload()}>Try again</Button></Card>
      : surveys === null ? <p role="status">Loading dashboard…</p>
      : surveys.length === 0 ? <GettingStarted />
      : <>
        <h2 className="section-header">Overview</h2>
        <Card className="front-overview" aria-labelledby="overall-statistics-title"><CardHeader id="overall-statistics-title" title="Overall statistics" actions={<ButtonLink size="sm" to="/results">View all results →</ButtonLink>} /><div className="front-stats">
          <div><span>Live surveys</span><strong>{live}</strong><Link to="/surveys?status=live">View surveys</Link></div>
          <div><span>Responses</span><strong>{responses}</strong><Link to="/responses">View responses</Link></div>
          <div><span>Surveys</span><strong>{surveys.length}</strong><Link to="/surveys">View all surveys</Link></div>
          <div><span>With results</span><strong>{withResults.length}</strong><Link to="/results">View performance</Link></div>
        </div></Card>
        <h2 className="section-header">Results</h2>
        <div className="front-results-grid">
          <Card aria-labelledby="latest-results-title"><CardHeader id="latest-results-title" title="Latest results" actions={<ButtonLink size="sm" to="/results">View all results →</ButtonLink>} />
            {withResults.length ? <ul className="front-result-list">{withResults.map((survey) => <li key={survey.id}><div><strong>{survey.title}</strong><small>{TYPE_LABEL[survey.type]} · {survey.answers} responses</small></div><div className="front-headline"><strong>{survey.headline?.score ?? `${survey.answers} responses`}</strong><small>{survey.headline?.note}</small></div><ButtonLink size="sm" to="/results">See results</ButtonLink></li>)}</ul>
              : <EmptyState icon={icons.chart} title="No results yet." text="Results will appear here after someone answers a survey." />}
          </Card>
          <Card aria-labelledby="contacted-title"><CardHeader id="contacted-title" title="Asked to be contacted" /><div className="front-contact-card"><p><strong>0</strong><span>respondents are waiting for a reply</span></p><p className="front-muted">New contact requests will appear here.</p><ButtonLink variant="primary" size="sm" to="/contact-requests">Open contact requests</ButtonLink></div></Card>
        </div>
        <h2 className="section-header">Your surveys</h2>
        <Card aria-labelledby="your-surveys-title"><CardHeader id="your-surveys-title" title="Your surveys" actions={<ButtonLink size="sm" to="/surveys">View all surveys →</ButtonLink>} /><Table caption="Your surveys" columns={columns} rows={recent} rowKey={(survey) => survey.id} /></Card>
      </>}
    <h2 className="section-header">News and inspiration</h2>
    <div className="front-news-grid"><Card aria-labelledby="recent-news-title"><CardHeader id="recent-news-title" title="Recent news" /><ArticleList items={NEWS} /></Card><Card aria-labelledby="inspiration-title"><CardHeader id="inspiration-title" title="Get inspired" /><ArticleList items={INSPIRATION} /></Card></div>
  </div>;
}
