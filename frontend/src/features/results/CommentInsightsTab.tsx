import { useEffect, useState, type FormEvent } from 'react';
import { api, type CommentInsights, type InsightSentiment, type InsightTheme } from '../../api/client';
import { Badge, Button, Card, EmptyState, TextButton, TextField, icons } from '../../components/ui';
import { BarList } from './charts/BarList';
import { plural, signed } from './format';

const SENTIMENTS: { key: keyof InsightSentiment; label: string }[] = [
  { key: 'negative', label: 'Negative' },
  { key: 'neutral', label: 'Neutral' },
  { key: 'positive', label: 'Positive' },
];

const SCORE_LABEL = { nps: 'NPS', thumbs: 'Positive', rating: 'Satisfied' } as const;

/** "+12" for NPS, "64%" for the percentage scores. */
function scoreText(kind: CommentInsights['kind'], score: number): string {
  return kind === 'nps' ? signed(score) : `${score}%`;
}

/** Negative, neutral and positive parts of one bar, with a text version for screen readers. */
function SentimentBar({ split, total }: { split: InsightSentiment; total: number }) {
  const text = SENTIMENTS.map((s) => `${s.label} ${split[s.key]}`).join(', ');
  return (
    <span className="insights-bar" role="img" aria-label={text} title={text}>
      {SENTIMENTS.map((s) =>
        split[s.key] ? (
          <span key={s.key} className={`tone-${s.key}`} style={{ width: `${(split[s.key] / total) * 100}%` }} />
        ) : null,
      )}
    </span>
  );
}

function Legend() {
  return (
    <ul className="chart-legend insights-legend">
      {SENTIMENTS.map((s) => (
        <li key={s.key}>
          <span className={`chart-swatch tone-${s.key}`} aria-hidden="true" />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

type Named = InsightTheme & { edited: boolean };

function ThemeDetail({
  theme,
  kind,
  total,
  onRename,
}: {
  theme: Named;
  kind: CommentInsights['kind'];
  total: number;
  onRename: (label: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(theme.label);
  useEffect(() => {
    setEditing(false);
    setDraft(theme.label);
  }, [theme.key, theme.label]);

  const save = (e: FormEvent) => {
    e.preventDefault();
    const label = draft.trim();
    if (label) onRename(label);
    setEditing(false);
  };

  return (
    <Card className="results-card insights-detail" aria-live="polite">
      <div className="results-card-head">
        {theme.outlier ? (
          <Badge tone="muted">Not a theme</Badge>
        ) : theme.edited ? (
          <Badge tone="neutral">Renamed by you</Badge>
        ) : (
          <span className="insights-ai-badge">AI-generated</span>
        )}
        {!theme.outlier && !editing ? (
          <TextButton onClick={() => setEditing(true)}>Rename</TextButton>
        ) : null}
      </div>
      {editing ? (
        <form className="insights-rename" onSubmit={save}>
          <TextField
            label="Theme name"
            value={draft}
            maxLength={60}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setEditing(false);
            }}
          />
          <Button type="submit" variant="primary" size="sm">Save</Button>
          <Button size="sm" onClick={() => setEditing(false)}>Cancel</Button>
        </form>
      ) : (
        <h3 className="insights-theme-title">{theme.label}</h3>
      )}
      <p className="insights-meta">
        {plural(theme.comments, 'comment', 'comments')} · {theme.percent ?? 0}% of all {total}
        {kind && theme.score !== null ? (
          <>
            {' · '}
            {SCORE_LABEL[kind]} {scoreText(kind, theme.score)}
            {theme.score_vs_all !== null ? ` (${signed(theme.score_vs_all)} vs all commenters)` : ''}
          </>
        ) : null}
      </p>
      <SentimentBar split={theme.sentiment} total={theme.comments} />

      {theme.quotes.length > 0 ? (
        <>
          <h4 className="insights-subtitle">Quotes</h4>
          <ul className="insights-quotes">
            {theme.quotes.map((q) => (
              <li key={q.comment_id}>
                <q>{q.text}</q>
                {q.summary ? <span className="insights-quote-summary">{q.summary}</span> : null}
                <span className="insights-verified">✓ Found word-for-word in the comments</span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {theme.hidden_quotes > 0 ? (
        <p className="insights-hidden">
          {plural(theme.hidden_quotes, 'suggested quote', 'suggested quotes')} hidden: not found word-for-word in the
          comments.
        </p>
      ) : null}

      <h4 className="insights-subtitle">Sample comments</h4>
      <ul className="insights-samples">
        {theme.samples.map((text, i) => (
          <li key={i}>{text}</li>
        ))}
      </ul>
    </Card>
  );
}

/** Themes in the survey's comments, with every number computed by the server. */
export function CommentInsightsTab({
  surveyId,
  segment,
  onReadAll,
}: {
  surveyId: string;
  segment: string;
  onReadAll: () => void;
}) {
  const [data, setData] = useState<CommentInsights | null>(null);
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});

  useEffect(() => {
    let active = true;
    setData(null);
    setFailed(false);
    api.commentInsights(surveyId, segment).then(
      (result) => {
        if (active) setData(result);
      },
      () => {
        if (active) setFailed(true);
      },
    );
    return () => {
      active = false;
    };
  }, [surveyId, segment, reload]);

  if (failed) {
    return (
      <Card padded role="alert" className="results-error">
        <strong>We couldn’t load the comment insights.</strong>
        <Button onClick={() => setReload((n) => n + 1)}>Try again</Button>
      </Card>
    );
  }
  if (!data) return <p role="status">Grouping comments into themes…</p>;
  if (data.status === 'too_few') {
    return (
      <EmptyState
        icon={icons.chart}
        title="Not enough comments yet"
        text={`Themes show up once the survey has ${data.min_comments} comments. It has ${data.comments} so far.`}
        actions={data.comments > 0 ? <Button onClick={onReadAll}>Read the comments</Button> : undefined}
      />
    );
  }

  const themes: Named[] = data.themes.map((t) => ({ ...t, label: names[t.key] ?? t.label, edited: t.key in names }));
  const current = themes.find((t) => t.key === selected) ?? themes[0];
  const max = Math.max(...themes.map((t) => t.comments));
  const negative = themes.reduce((n, t) => n + t.sentiment.negative, 0);
  const found = themes.filter((t) => !t.outlier).length;
  const labelOf = (key: string, fallback: string) => names[key] ?? fallback;

  const kpis = [
    {
      label: 'Comments analysed',
      value: data.comments.toLocaleString('en-US'),
      note: data.redacted ? `${data.redacted} with personal data hidden` : 'no personal data found',
    },
    { label: 'Themes found', value: String(found), note: data.mode === 'direct' ? 'from one AI batch' : 'grouped first, then named' },
    data.kind && data.score !== null
      ? { label: `${SCORE_LABEL[data.kind]} of commenters`, value: scoreText(data.kind, data.score), note: 'from their scores' }
      : null,
    {
      label: 'Negative comments',
      value: `${data.comments ? Math.round((negative / data.comments) * 100) : 0}%`,
      note: plural(negative, 'comment', 'comments'),
    },
  ].filter((k) => k !== null);

  return (
    <div className="results-overview insights">
      <p className="insights-intro">
        <span className="insights-ai-badge">AI-generated, editable</span>
        Theme names, summaries and quotes come from AI and you can rename themes. Every count, percentage and score is
        computed from the answers, and a quote is shown only when it is found word-for-word.
      </p>

      <ul className="results-kpis" aria-label="Summary">
        {kpis.map((k) => (
          <li key={k.label}>
            <Card className="results-kpi">
              <span className="results-kpi-label">{k.label}</span>
              <span className="results-kpi-value">{k.value}</span>
              <span className="results-kpi-note">{k.note}</span>
            </Card>
          </li>
        ))}
      </ul>

      <div className="insights-grid">
        <Card className="results-card">
          <div className="results-card-head">
            <h2 className="results-card-title">What people talk about</h2>
            <Legend />
          </div>
          <ul className="insights-themes">
            {themes.map((t) => (
              <li key={t.key}>
                <button
                  type="button"
                  className={t.outlier ? 'insights-theme insights-theme-other' : 'insights-theme'}
                  aria-pressed={t.key === current.key}
                  onClick={() => setSelected(t.key)}
                >
                  <span className="insights-theme-label">{t.label}</span>
                  <span className="insights-track" style={{ width: `${(t.comments / max) * 100}%` }}>
                    <SentimentBar split={t.sentiment} total={t.comments} />
                  </span>
                  <span className="insights-theme-count">
                    <strong>{t.comments}</strong> · {t.percent ?? 0}%
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
        <ThemeDetail
          theme={current}
          kind={data.kind}
          total={data.comments}
          onRename={(label) => setNames((n) => ({ ...n, [current.key]: label }))}
        />
      </div>

      <div className="results-row">
        {data.negative_themes.length > 0 ? (
          <Card className="results-card">
            <BarList
              label="Themes in negative comments"
              rows={data.negative_themes.map((t) => ({
                label: labelOf(t.key, t.label),
                count: t.count,
                percent: t.percent ?? 0,
              }))}
              note={`Share of the ${plural(negative, 'negative comment', 'negative comments')}.`}
            />
          </Card>
        ) : null}
        <Card className="results-card">
          <h2 className="results-card-title">How this was made</h2>
          <dl className="insights-run">
            <dt>Personal data</dt>
            <dd>Emails and phone numbers are hidden before AI reads the comments.</dd>
            <dt>Method</dt>
            <dd>
              {data.mode === 'direct'
                ? `Fewer than ${data.direct_limit} comments, so AI read them all in one batch.`
                : `${data.direct_limit} or more comments, so similar ones were grouped first and AI named each group.`}
            </dd>
            {data.run.grouper ? (
              <>
                <dt>Grouping</dt>
                <dd>{data.run.grouper}</dd>
              </>
            ) : null}
            <dt>AI</dt>
            <dd>
              {data.run.writer}, {plural(data.run.llm_calls, 'call', 'calls')}
            </dd>
            <dt>Sentiment</dt>
            <dd>From each reader’s score; AI decides only for mixed scores.</dd>
          </dl>
        </Card>
      </div>
    </div>
  );
}
