import { useEffect, useRef, useState } from 'react';
import { api, errorDetail, type Snippet } from '../../api/client';
import { Button, Card, CardHeader, TextField } from '../../components/ui';
import { useCopy } from './useCopy';

/** Same rule as the API's tag pattern: a lower-case slug of 1–40 characters. */
const TAG = /^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$/;
const TAG_ERROR = 'Use 1–40 lower-case letters, digits or dashes. Start and end with a letter or digit.';
/** Wait for a pause in typing before asking for a new snippet. */
const TYPING_PAUSE_MS = 400;

function tagError(value: string): string | null {
  return value === '' || TAG.test(value) ? null : TAG_ERROR;
}

/**
 * The LianaMailer snippet (#41): campaign and segment tags, the HTML to paste with Copy,
 * and how to paste it into LianaMailer. The campaign starts as the API's default.
 */
export function MailerSnippetCard({ surveyId }: { surveyId: string }) {
  const [campaign, setCampaign] = useState<string | null>(null);
  const [segment, setSegment] = useState('all');
  const [snippet, setSnippet] = useState<Snippet | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [copyState, copy] = useCopy();
  const shown = useRef<Snippet | null>(null);
  shown.current = snippet;

  const campaignError = campaign === null ? null : tagError(campaign);
  const segmentError = tagError(segment);
  const ready = campaign !== '' && segment !== '' && !campaignError && !segmentError;

  useEffect(() => {
    if (!ready) return;
    // Filling in the API's default campaign must not ask for the same snippet again.
    const last = shown.current;
    if (last && last.campaign === campaign && last.segment === segment) return;
    let active = true;
    // The first request has no campaign yet, so the API picks it; don't wait for that one.
    const wait = campaign === null ? 0 : TYPING_PAUSE_MS;
    const timer = setTimeout(() => {
      api.snippet(surveyId, { campaign: campaign ?? undefined, segment }).then(
        (made) => {
          if (!active) return;
          setSnippet(made);
          setProblem(null);
          if (campaign === null) setCampaign(made.campaign);
        },
        (error) => {
          if (!active) return;
          setSnippet(null);
          setProblem(errorDetail(error) ?? 'We couldn’t make the snippet. Please try again.');
        },
      );
    }, wait);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [surveyId, campaign, segment, ready]);

  // The shown snippet must match the tags in the fields, or someone copies the old one.
  const current = snippet && snippet.campaign === campaign && snippet.segment === segment ? snippet : null;

  // No snippet at all (e.g. a custom survey): only say why.
  if (campaign === null && problem) {
    return (
      <Card padded className="live-card">
        <CardHeader title="Newsletter snippet" />
        <p className="publish-error" role="alert">{problem}</p>
      </Card>
    );
  }

  return (
    <>
      <Card padded className="live-card">
        <CardHeader title="Newsletter snippet" />
        <p className="live-hint">Copy the snippet into your LianaMailer email. The email only contains links.</p>
        <div className="snippet-tags">
          <TextField
            label="Campaign tag"
            value={campaign ?? ''}
            disabled={campaign === null}
            error={campaign === '' ? 'Enter a campaign tag.' : campaignError}
            onChange={(e) => setCampaign(e.target.value)}
          />
          <TextField
            label="Segment tag"
            value={segment}
            error={segment === '' ? 'Enter a segment tag.' : segmentError}
            onChange={(e) => setSegment(e.target.value)}
          />
        </div>
        <p className="live-hint">
          Tags are added to every link so results can be compared by campaign and segment. Make one snippet per segment
          you send to, for example members.
        </p>
        {problem ? (
          <p className="publish-error" role="alert">{problem}</p>
        ) : (
          <div className="snippet-box">
            <div className="snippet-box-header">
              <span className="field-label">HTML for your email</span>
              <Button size="sm" disabled={!current} onClick={() => current && void copy(current.html)}>
                {copyState === 'copied' ? 'Copied' : 'Copy snippet'}
              </Button>
            </div>
            <pre className="snippet-code" aria-label="Snippet HTML" aria-busy={!current}>
              {current ? current.html : 'Making the snippet…'}
            </pre>
          </div>
        )}
        <p className="share-status" role="status">
          {copyState === 'copied'
            ? 'Snippet copied. Paste it into an HTML block in LianaMailer.'
            : copyState === 'failed'
              ? 'We couldn’t copy the snippet. Select the HTML and copy it yourself.'
              : ''}
        </p>
      </Card>
      <Card padded className="live-card">
        <CardHeader title="Paste it into LianaMailer" />
        <ol className="paste-steps">
          <li>Open your newsletter in LianaMailer.</li>
          <li>Add an HTML block where you want the question, usually at the bottom.</li>
          <li>Paste the snippet and send a test email to yourself.</li>
          <li>Tap an answer to check that the thank-you page opens.</li>
        </ol>
      </Card>
    </>
  );
}
