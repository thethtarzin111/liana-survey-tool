import { useEffect, useId, useState } from 'react';
import QRCode from 'qrcode';
import { Button, Card, CardHeader } from '../../components/ui';
import { slug } from '../../utils/slug';
import { useCopy } from './useCopy';

/** "Share outside email": the public link with Copy, and its QR code to show or download (#6). */
export function ShareLinkCard({ title, url }: { title: string; url: string }) {
  const linkId = useId();
  const [copyState, copy] = useCopy();
  const [qr, setQr] = useState<string | null>(null);
  const [qrFailed, setQrFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setQr(null);
    setQrFailed(false);
    // Large enough to print; error correction M survives small marks on posters.
    QRCode.toDataURL(url, { width: 512, margin: 2, errorCorrectionLevel: 'M' }).then(
      (data) => { if (active) setQr(data); },
      () => { if (active) setQrFailed(true); },
    );
    return () => { active = false; };
  }, [url]);

  return (
    <Card padded className="live-card">
      <CardHeader title="Share outside email" />
      <p className="live-hint">
        Use the public link or QR code in social media posts, on your website or in automation steps. No login needed.
      </p>
      <div className="share-row">
        <div className="share-link">
          <label className="field-label" htmlFor={linkId}>Public link</label>
          <div className="share-link-input">
            <input
              id={linkId}
              className="input"
              type="text"
              readOnly
              value={url}
              onFocus={(e) => e.currentTarget.select()}
            />
            <Button onClick={() => void copy(url)}>{copyState === 'copied' ? 'Copied' : 'Copy link'}</Button>
          </div>
          <p className="share-status" role="status">
            {copyState === 'copied' ? 'Link copied' : copyState === 'failed' ? 'We couldn’t copy the link. Select it and copy it yourself.' : ''}
          </p>
        </div>
        <div className="share-qr">
          {qr ? (
            <>
              <img src={qr} alt="QR code for the public link" width={128} height={128} />
              <a className="btn btn-secondary btn-sm" href={qr} download={`${slug(title)}-qr.png`}>
                Download QR code
              </a>
            </>
          ) : qrFailed ? (
            <p role="alert">We couldn’t make the QR code.</p>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
