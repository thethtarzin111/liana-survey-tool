import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { api, type ResponseDetail as Detail } from '../../api/client';
import { IconButton, Tag, icons } from '../../components/ui';
import { THUMBS_LABEL } from './groups';
import { dayDate } from './format';

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

type Answer = Detail['answers'][number];

function valueText(a: Answer): string {
  if (a.value === null || a.value === '' || (Array.isArray(a.value) && a.value.length === 0)) return 'No answer';
  if (Array.isArray(a.value)) return a.value.join(', ');
  if (a.kind === 'thumbs') return THUMBS_LABEL[String(a.value)] ?? String(a.value);
  return String(a.value);
}

type Props = {
  surveyId: string;
  responseId: string;
  /** Gets focus back when the panel closes. */
  returnTo: HTMLElement | null;
  onClose: () => void;
};

/**
 * Side panel with every answer of one response, masked the same way as the table.
 * Focus moves in on open, stays inside, and returns to the row's button on close.
 */
export function ResponseDetail({ surveyId, responseId, returnTo, onClose }: Props) {
  const titleId = useId();
  const box = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    closeButton.current?.focus();
    return () => returnTo?.focus?.();
  }, [returnTo]);

  useEffect(() => {
    let active = true;
    setDetail(null);
    setFailed(false);
    api.responseDetail(surveyId, responseId).then(
      (d) => { if (active) setDetail(d); },
      () => { if (active) setFailed(true); },
    );
    return () => { active = false; };
  }, [surveyId, responseId]);

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      onClose();
      return;
    }
    if (e.key !== 'Tab' || !box.current) return;
    const items = Array.from(box.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  return createPortal(
    <div
      className="dialog-scrim response-scrim"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div ref={box} className="response-panel" role="dialog" aria-modal="true" aria-labelledby={titleId} onKeyDown={onKeyDown}>
        <div className="response-panel-head">
          <div>
            <h2 className="dialog-title" id={titleId}>
              {detail ? `Response ${detail.display_id}` : 'Response'}
            </h2>
            {detail ? (
              <p className="response-panel-meta">
                {dayDate(detail.submitted_at)}
                {detail.segment_label ? ` · ${detail.segment_label}` : ''}
              </p>
            ) : null}
            {detail?.contact_requested ? (
              <p className="response-panel-meta">
                <Tag>Contact me</Tag> {detail.contact ?? ''}
              </p>
            ) : null}
          </div>
          <IconButton ref={closeButton} label="Close" icon={icons.close} onClick={onClose} />
        </div>
        {failed ? (
          <p role="alert">We couldn’t load this response.</p>
        ) : !detail ? (
          <p role="status">Loading response…</p>
        ) : (
          <dl className="response-answers">
            {detail.answers.map((a) => (
              <div key={a.question_id} className="response-answer">
                <dt>{a.prompt}</dt>
                <dd>
                  {valueText(a)}
                  {a.masked ? <Tag>Personal details hidden</Tag> : null}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </div>,
    document.body,
  );
}
