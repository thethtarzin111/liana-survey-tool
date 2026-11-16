import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, type Survey } from '../../api/client';
import { PageHeader } from '../../components/PageHeader';
import { Button, Card, SurveyStatusBadge } from '../../components/ui';
import { surveyTypes } from './surveyTypes';
import './builder.css';

export function BuilderPage() {
  const { id = '' } = useParams();
  const [survey, setSurvey] = useState<Survey | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setSurvey(null);
    setError(false);
    api.survey(id).then(
      (saved) => { if (active) setSurvey(saved); },
      () => { if (active) setError(true); },
    );
    return () => { active = false; };
  }, [id, attempt]);

  return (
    <>
      <PageHeader title="Build your survey" description={survey?.title} />
      {error ? (
        <div className="survey-error" role="alert">
          <p>We couldn’t load this survey. Please try again.</p>
          <Button onClick={() => setAttempt((value) => value + 1)}>Try again</Button>
        </div>
      ) : survey ? (
        <>
          <div className="survey-draft-meta">
            <SurveyStatusBadge status={survey.status} />
            <span>{surveyTypes.find((option) => option.type === survey.type)?.title}</span>
          </div>
          <Card padded>
            <p>Your draft is saved. Question editing will be available here next.</p>
          </Card>
        </>
      ) : <p role="status">Loading your survey…</p>}
    </>
  );
}
