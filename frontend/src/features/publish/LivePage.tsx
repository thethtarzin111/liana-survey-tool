import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError, type Survey } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { ButtonLink, Card, CardHeader } from '../../components/ui';
import { ANSWERS, type OneTapType } from './answers';
import { MailerSnippetCard } from './MailerSnippetCard';
import { ShareLinkCard } from './ShareLinkCard';
import { SurveySettingsCard } from './SurveySettingsCard';
import './publish.css';

/** "<name> is live": share the survey once it is published (#117; prototype "Survey is live"). */
export function LivePage() {
  const { id = '' } = useParams();
  const [survey, setSurvey] = useState<Survey | null>(null);
  const [loadError, setLoadError] = useState<'not-found' | 'failed' | null>(null);

  useEffect(() => {
    let active = true;
    setSurvey(null);
    setLoadError(null);
    api.survey(id).then(
      (saved) => { if (active) setSurvey(saved); },
      (error) => {
        if (active) setLoadError(error instanceof ApiError && error.status === 404 ? 'not-found' : 'failed');
      },
    );
    return () => { active = false; };
  }, [id]);

  if (loadError) {
    return (
      <div className="publish-problem" role="alert">
        <p>{loadError === 'not-found' ? 'Survey not found.' : 'We couldn’t load the survey. Please try again.'}</p>
        <Link to="/surveys">Back to surveys</Link>
      </div>
    );
  }
  if (!survey) return <p role="status">Loading survey…</p>;
  if (survey.status !== 'live' || !survey.public_url) {
    return (
      <div className="publish-problem" role="alert">
        <p>“{survey.title}” is not live, so it has no working link yet.</p>
        <Link to={`/surveys/${encodeURIComponent(survey.id)}`}>Edit the survey</Link>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title={`${survey.title} is live`}
        description="Share the link to start collecting answers."
        actions={
          <div className="live-actions">
            <ButtonLink to={`/results?survey=${encodeURIComponent(survey.id)}`} variant="secondary">See results</ButtonLink>
            <ButtonLink to={`/surveys/${encodeURIComponent(survey.id)}`} variant="ghost">Edit survey</ButtonLink>
            <ButtonLink to="/surveys" variant="secondary">Back to surveys</ButtonLink>
          </div>
        }
      />
      <div className="live-columns">
        <div className="live-layout">
          <MailerSnippetCard surveyId={survey.id} />
          <ShareLinkCard title={survey.title} url={survey.public_url} />
          {import.meta.env.DEV ? <TryAsReader survey={survey} /> : null}
        </div>
        <aside className="live-side">
          <SurveySettingsCard survey={survey} onSaved={setSurvey} />
        </aside>
      </div>
    </>
  );
}

/** Local development only: signed links for made-up readers, one per answer. */
export function TryAsReader({ survey }: { survey: Survey }) {
  const [links, setLinks] = useState<string[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    api.testLinks(survey.id).then(
      (made) => { if (active) setLinks(made.links); },
      // 404 outside local development: show nothing.
      (error) => { if (active && !(error instanceof ApiError && error.status === 404)) setFailed(true); },
    );
    return () => { active = false; };
  }, [survey.id]);

  if (!links && !failed) return null;
  return (
    <Card padded className="live-card try-reader">
      <CardHeader title="Try it as a reader" />
      <p className="live-hint">
        Local development only. Each reader gets their own link, as in an email. Open an answer in a private
        window: you see the thank-you page, and the survey counts it once per reader.
      </p>
      {failed ? (
        <p role="alert">We couldn’t make test links. Please reload the page.</p>
      ) : survey.type === 'custom' ? (
        <p>Custom surveys are answered on the survey page, which isn’t built yet.</p>
      ) : (
        <ol className="reader-list">
          {links!.map((link, i) => (
            <li key={link}>
              <span className="reader-name">Reader {i + 1}</span>
              <span className="reader-answers">
                {ANSWERS[survey.type as OneTapType].map((answer) => (
                  <a
                    key={answer.value}
                    className="reader-answer"
                    href={`${link}&a=${answer.value}`}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`Reader ${i + 1} answers ${answer.label}`}
                  >
                    {answer.label}
                  </a>
                ))}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
