import { useEffect, useState, type ReactNode } from 'react';
import { api, type SurveyListItem, type SurveyStatus, type SurveyType } from '../../api/client';
import { Icon } from '../../components/Icon';
import {
  Button,
  ButtonLink,
  Card,
  CardHeader,
  EmptyState,
  IconCircle,
  SurveyStatusBadge,
  Table,
  icons,
  type Column,
} from '../../components/ui';
import { dayDate } from '../results/format';
import { useFeatureFlag } from '../settings/featureFlags';
import { LatestSplit } from './LatestSplit';
import { PerformancePanel } from './PerformancePanel';
import { WelcomeBanner } from './WelcomeBanner';
import './front.css';

const TYPE_LABEL: Record<SurveyType, string> = {
  thumbs: 'Thumbs rating',
  nps: 'NPS survey',
  csat: 'CSAT survey',
  custom: 'Custom survey',
};
const STATUS_LABEL: Record<SurveyStatus, string> = {
  draft: 'Draft',
  scheduled: 'Scheduled',
  live: 'Live',
  closed: 'Closed',
};
const BLOG = 'https://www.lianatech.com/resources/blog/';

type Article = { title: string; date: string; icon?: string; tone?: 'brand' | 'muted' };
const NEWS: Article[] = [
  { title: 'Introducing LianaSurvey: surveys that work with your other Liana tools', date: 'Sat 14/11/2026' },
  { title: 'New: share surveys with a QR code or embed them on your website', date: 'Tue 10/11/2026' },
  { title: 'Survey templates now in Finnish, Swedish and English', date: 'Wed 04/11/2026' },
];
const INSPIRATION: Article[] = [
  { title: 'How to write a good NPS question', date: 'Thu 12/11/2026', icon: icons.star, tone: 'brand' },
  {
    title: 'Close the loop with LianaAutomation: reply to every “Not for me”',
    date: 'Thu 29/10/2026',
    icon: icons.loop,
    tone: 'brand',
  },
  {
    title: 'Short surveys get more answers: keep it to three questions',
    date: 'Fri 16/10/2026',
    icon: icons.list,
    tone: 'muted',
  },
];

function closesText(survey: SurveyListItem): string {
  switch (survey.status) {
    case 'scheduled':
      return survey.opens_at ? `Opens ${dayDate(survey.opens_at)}` : 'Not set';
    case 'live':
      return survey.closes_at ? dayDate(survey.closes_at) : 'No end date';
    case 'closed':
      return survey.closes_at ? `Closed ${dayDate(survey.closes_at)}` : 'Closed';
    default:
      return 'Not set';
  }
}

/** Live surveys open their "is live" page; the rest open the editor. */
function surveyPath(survey: SurveyListItem): string {
  const path = `/surveys/${encodeURIComponent(survey.id)}`;
  return survey.status === 'live' ? `${path}/live` : path;
}

function resultsPath(survey: SurveyListItem): string {
  return `/results?survey=${encodeURIComponent(survey.id)}`;
}

/** "NPS +31" stays whole; "84% positive" becomes "84%" over "positive". */
function splitScore(survey: SurveyListItem): { big: string; small: string } {
  const headline = survey.headline;
  if (!headline) return { big: String(survey.answers), small: survey.answers === 1 ? 'answer' : 'answers' };
  const match = /^(NPS )?([+−-]?\d+%?)\s*(.*)$/.exec(headline.score);
  if (!match) return { big: headline.score, small: headline.note };
  return { big: `${match[1] ?? ''}${match[2]}`, small: match[3] || headline.note };
}

function GettingStarted({ surveys }: { surveys: SurveyListItem[] }) {
  const made = surveys.length > 0;
  const shared = surveys.some((survey) => survey.status === 'live');
  const step = (done: boolean, n: number, title: string, hint: string, action?: ReactNode) => (
    <li className={done ? 'done' : undefined}>
      <span className="front-step-mark" aria-hidden="true">
        {done ? <Icon path={icons.check} size={14} /> : n}
      </span>
      <div>
        <strong>
          {title}
          {done ? <span className="visually-hidden"> (done)</span> : null}
        </strong>
        <small>{hint}</small>
      </div>
      {action}
    </li>
  );
  return (
    <Card className="front-getting-started" aria-labelledby="getting-started-title">
      <div>
        <h2 className="card-title" id="getting-started-title">Get started with LianaSurvey</h2>
        <p className="front-muted">Three steps to your first results. It takes about 5 minutes.</p>
      </div>
      <ol className="front-steps">
        {step(made, 1, 'Create your first survey', 'Start from a template or write your own questions.',
          <ButtonLink to="/surveys/new" variant="primary" size="sm">Create survey</ButtonLink>)}
        {step(shared, 2, 'Send it to respondents',
          'Paste the snippet into a LianaMailer message, or share the link or QR code.',
          <ButtonLink to="/integrations" size="sm">See sharing options</ButtonLink>)}
        {step(false, 3, 'Watch the answers come in',
          'Results and comments show up here as soon as people answer.')}
      </ol>
    </Card>
  );
}

function ArticleCard({ id, title, items }: { id: string; title: string; items: Article[] }) {
  return (
    <Card aria-labelledby={id}>
      <CardHeader
        id={id}
        title={title}
        actions={
          <a className="btn btn-secondary btn-sm" href={BLOG} target="_blank" rel="noreferrer">
            View all ↗
          </a>
        }
      />
      <ul className="front-links">
        {items.map((item) => (
          <li key={item.title}>
            {item.icon ? (
              <span className={`front-thumb front-thumb-${item.tone}`} aria-hidden="true">
                <Icon path={item.icon} size={24} />
              </span>
            ) : null}
            <span>
              <a href={BLOG} target="_blank" rel="noreferrer">
                {item.title} ↗
              </a>
              <small>{item.date}</small>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function FrontPage() {
  const [showNews] = useFeatureFlag('newsAndInspiration');
  const [surveys, setSurveys] = useState<SurveyListItem[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    api.listSurveys().then(
      (rows) => { if (active) setSurveys(Array.isArray(rows) ? rows : []); },
      () => { if (active) setFailed(true); },
    );
    return () => { active = false; };
  }, []);

  if (failed) {
    return (
      <div className="front-page">
        <WelcomeBanner />
        <Card padded className="front-error" role="alert">
          <strong>We couldn’t load your dashboard.</strong>
          <p>Your survey information is temporarily unavailable.</p>
          <Button onClick={() => window.location.reload()}>Try again</Button>
        </Card>
      </div>
    );
  }
  if (surveys === null) {
    return (
      <div className="front-page">
        <WelcomeBanner />
        <p role="status">Loading dashboard…</p>
      </div>
    );
  }

  const answered = surveys.filter((survey) => survey.answers > 0);
  const live = surveys.filter((survey) => survey.status === 'live').length;
  const responses = surveys.reduce((sum, survey) => sum + survey.answers, 0);
  const nps = answered.find((survey) => survey.type === 'nps' && survey.headline);

  const stats = [
    { label: 'Live surveys', icon: icons.list, value: String(live), note: '', cta: 'View surveys', to: '/surveys?status=live' },
    { label: 'Responses', icon: icons.message, value: String(responses), note: '', cta: 'View responses', to: '/results?tab=responses' },
    // Needs the sent and viewed counts from survey performance (#12).
    { label: 'Average response rate', icon: icons.trend, value: '—', note: 'live surveys', cta: 'View performance', to: '/results' },
    {
      label: 'Member NPS',
      icon: icons.star,
      value: nps?.headline ? nps.headline.score.replace('NPS ', '') : '—',
      note: nps ? 'scale −100 to +100' : 'no answers yet',
      cta: 'View NPS results',
      to: nps ? resultsPath(nps) : '/results',
    },
  ];

  const columns: Column<SurveyListItem>[] = [
    {
      key: 'title',
      header: 'Survey',
      render: (survey) => (
        <div>
          <strong>{survey.title}</strong>
          <small>{TYPE_LABEL[survey.type]}</small>
        </div>
      ),
    },
    { key: 'status', header: 'Status', render: (survey) => <SurveyStatusBadge status={survey.status} /> },
    { key: 'answers', header: 'Responses', numeric: true },
    { key: 'closes', header: 'Closes', render: closesText },
    {
      key: 'open',
      header: 'Action',
      hideHeader: true,
      render: (survey) => <ButtonLink size="sm" to={surveyPath(survey)}>Open</ButtonLink>,
    },
  ];

  return (
    <div className="front-page">
      <WelcomeBanner />
      {answered.length === 0 ? <GettingStarted surveys={surveys} /> : null}

      <h2 className="section-header">Overview</h2>
      <Card aria-labelledby="overall-statistics-title">
        <CardHeader
          id="overall-statistics-title"
          title="Overall statistics"
          actions={<ButtonLink size="sm" to="/results">View all results →</ButtonLink>}
        />
        <div className="front-stats">
          {stats.map((stat) => (
            <div key={stat.label}>
              <IconCircle icon={stat.icon} size={76} />
              <span className="front-stat-label">{stat.label}</span>
              <span>
                <strong>{stat.value}</strong> {stat.note ? <small>{stat.note}</small> : null}
              </span>
              <ButtonLink size="sm" to={stat.to}>{stat.cta}</ButtonLink>
            </div>
          ))}
        </div>
      </Card>

      <h2 className="section-header">Results</h2>
      <div className="front-results-grid">
        <Card aria-labelledby="latest-results-title">
          <CardHeader
            id="latest-results-title"
            title="Latest results"
            actions={<ButtonLink size="sm" to="/results">View all results →</ButtonLink>}
          />
          {answered.length ? (
            <ul className="front-result-list">
              {answered.slice(0, 3).map((survey) => {
                const score = splitScore(survey);
                return (
                  <li key={survey.id}>
                    <div>
                      <strong>{survey.title}</strong>
                      <small>
                        {TYPE_LABEL[survey.type]} · {survey.answers} answers · {STATUS_LABEL[survey.status]}
                      </small>
                    </div>
                    <LatestSplit survey={survey} />
                    <div className="front-headline">
                      <strong>{score.big}</strong>
                      <small>{score.small}</small>
                    </div>
                    <ButtonLink size="sm" to={resultsPath(survey)}>See results</ButtonLink>
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState
              icon={icons.chart}
              title="No results yet"
              text="Results show up here as soon as respondents start answering your surveys."
            />
          )}
        </Card>
      </div>

      <h2 className="section-header">Your surveys</h2>
      <Card aria-labelledby="your-surveys-title">
        <CardHeader
          id="your-surveys-title"
          title="Your surveys"
          actions={<ButtonLink size="sm" to="/surveys">View all surveys →</ButtonLink>}
        />
        {surveys.length ? (
          <Table caption="Your surveys" columns={columns} rows={surveys.slice(0, 4)} rowKey={(survey) => survey.id} />
        ) : (
          <EmptyState
            icon={icons.list}
            title="No surveys yet"
            text="Create a survey from a template in a couple of minutes, or build your own."
            actions={
              <>
                <ButtonLink to="/surveys/new" variant="primary" icon={icons.plus}>Create survey</ButtonLink>
                <ButtonLink to="/templates">Browse templates</ButtonLink>
              </>
            }
          />
        )}
      </Card>

      <h2 className="section-header">Reports</h2>
      <PerformancePanel />

      {/* Optional, off by default: Settings > Feature flags (#153). */}
      {showNews ? (
        <>
          <h2 className="section-header">News and inspiration</h2>
          <div className="front-news-grid">
            <ArticleCard id="recent-news-title" title="Recent news" items={NEWS} />
            <ArticleCard id="inspiration-title" title="Get inspired" items={INSPIRATION} />
          </div>
        </>
      ) : null}
    </div>
  );
}
