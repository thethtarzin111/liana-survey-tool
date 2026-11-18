import { useState } from 'react';
import { ButtonLink } from '../../components/ui';

export function WelcomeBanner() {
  const [open, setOpen] = useState(true);
  return <section className={`welcome-banner ${open ? '' : 'welcome-collapsed'}`} aria-labelledby="welcome-title">
    <button className="welcome-toggle" aria-label={open ? 'Collapse welcome banner' : 'Expand welcome banner'} aria-expanded={open} aria-controls="welcome-content" onClick={() => setOpen(!open)}>{open ? '⌃' : '⌄'}</button>
    <div className="welcome-content" id="welcome-content" hidden={!open}>
      <div className="welcome-copy"><span>LianaSurvey</span><h1 id="welcome-title">Welcome to LianaSurvey – hear what your readers think</h1><p>Create a one-tap rating, an NPS or CSAT question, or a full survey. Send it in an email, share a link or QR code, and follow up on every answer automatically.</p><div className="front-actions"><ButtonLink to="/surveys/new" variant="primary">Create survey</ButtonLink><ButtonLink to="/templates">Browse templates</ButtonLink></div></div>
      <div className="welcome-art" aria-hidden="true"><div className="welcome-newsletter"><div><strong>May newsletter</strong><small>Example association</small></div><i /><i /><i /><div className="welcome-rating"><strong>How was this newsletter?</strong><div><span>Not for me</span><span>Good</span><span>Loved it</span></div></div></div><div className="welcome-result"><small>Latest result</small><strong>84% positive</strong><small>214 answers</small></div></div>
    </div>
    {!open ? <p className="welcome-short">LianaSurvey · Welcome to LianaSurvey – hear what your readers think</p> : null}
  </section>;
}
