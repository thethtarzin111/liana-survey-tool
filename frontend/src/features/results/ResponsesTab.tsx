import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError, responsesCsvUrl, type ResponseRow } from '../../api/client';
import { Button, Card, EmptyState, SearchInput, Tag, ToggleChip, icons } from '../../components/ui';
import { Icon } from '../../components/Icon';
import { THUMBS_LABEL } from './groups';
import { plural, relativeTime } from './format';
import { ResponseDetail } from './ResponseDetail';
import { useResultsParams } from './useResultsParams';

export type Scale = 'nps' | 'thumbs' | 'rating';

const PAGE = 50;

const CHIPS: Record<Scale, { group: string; label: string }[]> = {
  thumbs: [
    { group: 'not-for-me', label: 'Not for me' },
    { group: 'good', label: 'Good' },
    { group: 'loved-it', label: 'Loved it' },
  ],
  nps: [
    { group: 'detractors', label: 'Detractors' },
    { group: 'passives', label: 'Passives' },
    { group: 'promoters', label: 'Promoters' },
  ],
  rating: [
    { group: 'low', label: '1–2' },
    { group: 'neutral', label: '3' },
    { group: 'high', label: '4–5' },
  ],
};

type Page = { key: string; rows: ResponseRow[]; total: number };

const answerText = (row: ResponseRow, scale: Scale | null) =>
  row.answer === null ? '—' : scale === 'thumbs' ? (THUMBS_LABEL[String(row.answer)] ?? String(row.answer)) : String(row.answer);

type Props = {
  surveyId: string;
  segment: string;
  /** The survey's first scale question; its answers fill the Answer column and the chips. Null for none. */
  scale: Scale | null;
};

/** Every response of one survey, newest first, with search, answer-group chips and a side panel per response. */
export function ResponsesTab({ surveyId, segment, scale }: Props) {
  const { q, group: urlGroup, set } = useResultsParams();
  const [draft, setDraft] = useState(q);
  const [page, setPage] = useState<Page | null>(null);
  const [failed, setFailed] = useState<'refused' | 'error' | null>(null);
  const [more, setMore] = useState<'idle' | 'busy' | 'failed'>('idle');
  const [reload, setReload] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const trigger = useRef<HTMLElement | null>(null);

  const chips = scale ? CHIPS[scale] : [];
  // A group from a stale or shared link that this survey has no chip for is never sent.
  const group = chips.some((c) => c.group === urlGroup) ? urlGroup : '';
  useEffect(() => {
    if (urlGroup && !group) set({ group: '' }, { replace: true });
  }, [urlGroup, group, set]);

  const key = JSON.stringify([surveyId, segment, q, group]);
  const keyRef = useRef(key);
  keyRef.current = key;

  useEffect(() => setDraft(q), [q]);

  useEffect(() => {
    let active = true;
    setFailed(null);
    setMore('idle');
    api.responses(surveyId, { segment, q, group, limit: PAGE, offset: 0 }).then(
      (data) => { if (active) setPage({ key, rows: data.rows, total: data.total }); },
      (error: unknown) => {
        if (!active) return;
        setFailed(error instanceof ApiError && (error.status === 400 || error.status === 422) ? 'refused' : 'error');
      },
    );
    return () => { active = false; };
  }, [key, surveyId, segment, q, group, reload]);

  const current = page && page.key === key ? page : null;

  const loadMore = () => {
    if (!current) return;
    setMore('busy');
    api.responses(surveyId, { segment, q, group, limit: PAGE, offset: current.rows.length }).then(
      (data) => {
        setPage((prev) => (prev && prev.key === key ? { ...prev, rows: [...prev.rows, ...data.rows], total: data.total } : prev));
        if (keyRef.current === key) setMore('idle');
      },
      () => { if (keyRef.current === key) setMore('failed'); },
    );
  };

  const open = (id: string, from: HTMLElement | null) => {
    trigger.current = from;
    setOpenId(id);
  };

  /** A click anywhere on a row opens it, like its ID button does. */
  const onTableClick = (e: MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.closest('button, a')) return;
    const button = target.closest('tbody tr')?.querySelector<HTMLButtonElement>('button.response-open');
    button?.click();
  };

  const filtered = Boolean(q || group);
  const toolbar = (
    <div className="responses-toolbar">
      <SearchInput label="Search comments" placeholder="Search comments…" value={draft} onChange={setDraft} onSearch={(v) => set({ q: v.trim() })} />
      {chips.length ? (
        <div className="responses-chips" role="group" aria-label="Answer group">
          <ToggleChip selected={!group} onChange={() => set({ group: '' })}>All answers</ToggleChip>
          {chips.map((c) => (
            <ToggleChip key={c.group} selected={group === c.group} onChange={(on) => set({ group: on ? c.group : '' })}>
              {c.label}
            </ToggleChip>
          ))}
        </div>
      ) : null}
      <a
        className="btn btn-secondary responses-export"
        href={responsesCsvUrl(surveyId, { segment, q, group })}
        download
      >
        <Icon path={icons.list} size={16} />
        Export CSV
      </a>
    </div>
  );

  const notice = (
    <p className="responses-notice">
      <Icon path={icons.info} size={16} />
      <span>
        Anonymised. No names or emails are shown. Emails and phone numbers typed into comments are hidden automatically.
        People who asked to be contacted are in <Link to="/contact-requests">Contact requests</Link>.
      </span>
    </p>
  );

  let body;
  if (failed === 'refused') {
    body = (
      <Card>
        <EmptyState
          icon={icons.search}
          title="No responses match."
          actions={<Button onClick={() => set({ q: '', group: '' })}>Clear filters</Button>}
        />
      </Card>
    );
  } else if (failed) {
    body = (
      <Card padded role="alert" className="results-error">
        <strong>We couldn’t load the responses.</strong>
        <Button onClick={() => setReload((n) => n + 1)}>Try again</Button>
      </Card>
    );
  } else if (!current) {
    body = <p role="status">Loading responses…</p>;
  } else if (current.total === 0) {
    body = (
      <Card>
        {filtered ? (
          <EmptyState
            icon={icons.search}
            title="No responses match."
            actions={<Button onClick={() => set({ q: '', group: '' })}>Clear filters</Button>}
          />
        ) : (
          <EmptyState
            icon={icons.message}
            title="No responses yet"
            text="Answers show up here as soon as people reply."
          />
        )}
      </Card>
    );
  } else {
    body = (
      <>
        <div className="table-wrap responses-table" onClick={onTableClick}>
          <table className="table table-stack">
            <caption className="visually-hidden">Responses, newest first</caption>
            <thead>
              <tr>
                {['ID', 'Received', 'Answer', 'Reason', 'Comment', 'Segment'].map((h) => (
                  <th key={h} scope="col">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {current.rows.map((r) => (
                <tr key={r.id} className="response-row">
                  <td data-label="ID">
                    <button type="button" className="response-open" onClick={(e) => open(r.id, e.currentTarget)}>
                      {r.display_id}
                    </button>
                  </td>
                  <td data-label="Received">
                    <time dateTime={r.submitted_at} title={new Date(r.submitted_at).toLocaleString('en-GB')}>
                      {relativeTime(r.submitted_at)}
                    </time>
                  </td>
                  <td data-label="Answer">{answerText(r, scale)}</td>
                  <td data-label="Reason">{r.reason ?? '—'}</td>
                  <td data-label="Comment">
                    {r.comment ? <span className="response-comment">{r.comment}</span> : '—'}
                    {r.masked ? <Tag>Personal details hidden</Tag> : null}
                  </td>
                  <td data-label="Segment">{r.segment_label ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="responses-foot">
          <span>
            Showing {current.rows.length} of {plural(current.total, 'response', 'responses')}, newest first
          </span>
          {current.rows.length < current.total ? (
            <Button onClick={loadMore} loading={more === 'busy'}>Load more</Button>
          ) : null}
          {more === 'failed' ? <span role="alert">We couldn’t load more responses.</span> : null}
        </div>
      </>
    );
  }

  return (
    <div className="results-responses">
      {toolbar}
      {notice}
      {body}
      {openId ? (
        <ResponseDetail
          surveyId={surveyId}
          responseId={openId}
          returnTo={trigger.current}
          onClose={() => setOpenId(null)}
        />
      ) : null}
    </div>
  );
}
