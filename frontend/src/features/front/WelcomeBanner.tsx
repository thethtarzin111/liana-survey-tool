import { useState } from 'react';
import { Icon } from '../../components/Icon';
import { ButtonLink, IconButton, icons } from '../../components/ui';

const HEADING = 'Welcome to LianaSurvey – hear what your readers think';
const STORAGE_KEY = 'lianasurvey.welcomeBanner';

/** Folded state is a per-browser convenience: blocked storage means the banner starts open. */
function readFolded(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'folded';
  } catch {
    return false;
  }
}

function saveFolded(folded: boolean) {
  try {
    if (folded) window.localStorage.setItem(STORAGE_KEY, 'folded');
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked: the choice lasts until the page reloads.
  }
}

export function WelcomeBanner() {
  const [folded, setFolded] = useState(readFolded);
  const toggle = () => {
    saveFolded(!folded);
    setFolded(!folded);
  };

  return (
    <section className={`welcome-banner${folded ? ' folded' : ''}`} aria-labelledby="welcome-title">
      <IconButton
        className="welcome-toggle"
        label={folded ? 'Show the welcome banner' : 'Fold up the welcome banner'}
        icon={folded ? icons.chevronDown : icons.close}
        aria-expanded={!folded}
        aria-controls="welcome-body"
        onClick={toggle}
      />
      <div id="welcome-body" className={`welcome-body${folded ? ' folded' : ''}`}>
        <div>
          <div className="welcome-inner">
            <div className="welcome-copy">
              <span className="welcome-brand">
                <Icon path={icons.message} size={18} />
                LianaSurvey
              </span>
              <h1 id="welcome-title">{HEADING}</h1>
              <p>
                Create a one-tap rating, an NPS or CSAT question, or a full survey. Send it in an email, share a
                link or QR code, and follow up on every answer automatically.
              </p>
              <div className="welcome-actions">
                <ButtonLink to="/surveys/new" variant="primary">Create survey</ButtonLink>
                <ButtonLink to="/templates">Browse templates</ButtonLink>
              </div>
            </div>
            <div className="welcome-art" aria-hidden="true">
              <div className="welcome-mail">
                <div className="welcome-mail-head">
                  <strong>May newsletter</strong>
                  <span>Example Members Association</span>
                </div>
                <i />
                <i />
                <i />
                <div className="welcome-rating">
                  <strong>How was this newsletter?</strong>
                  <div>
                    <span>Not for me</span>
                    <span className="on">Good</span>
                    <span>Loved it</span>
                  </div>
                </div>
              </div>
              <div className="welcome-result">
                <span>Latest result</span>
                <strong>84% positive</strong>
                <span>214 answers</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
