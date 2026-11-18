import { useEffect, useState } from 'react';
import { api, type PerformanceRow } from '../../api/client';

import { Button, Card, CardHeader, EmptyState, Table, icons, type Column } from '../../components/ui';

const CHANNEL = { email: 'Email', link: 'Link', qr: 'QR code' } as const;

export function PerformancePanel() {
  const [rows, setRows] = useState<PerformanceRow[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    const load = () => {
      setFailed(false);
      api.performance().then((data) => { if (active) setRows(data); }, () => { if (active) setFailed(true); });
    };
    load();
    const timer = window.setInterval(load, 30_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [reload]);

  const columns: Column<PerformanceRow>[] = [
    { key: 'survey', header: 'Survey' },
    { key: 'channel', header: 'Channel', render: (row) => CHANNEL[row.channel] },
    { key: 'views', header: 'Sent or viewed', numeric: true },
    { key: 'responses', header: 'Responses', numeric: true },
    { key: 'rate', header: 'Response rate', numeric: true, render: (row) => row.response_rate === null ? '—' : `${row.response_rate}%` },
    { key: 'main_result', header: 'Main result', render: (row) => row.main_result ?? '—' },
  ];

  let content;
  if (failed) content = <Card padded role="alert"><p>We couldn’t load survey performance.</p><Button onClick={() => setReload((n) => n + 1)}>Try again</Button></Card>;
  else if (rows === null) content = <p role="status">Loading performance…</p>;
  else if (rows.length === 0) content = <Card><EmptyState icon={icons.chart} title="No performance data yet." text="Views and responses will appear after you share a survey." /></Card>;
  else content = <Card><Table caption="Survey performance" columns={columns} rows={rows} rowKey={(row) => `${row.survey_id}-${row.channel}`} /></Card>;

  return <section aria-labelledby="performance-title"><CardHeader id="performance-title" title="Survey performance" /><p className="field-hint">Responses and the main result for each survey, by channel</p>{content}</section>;
}
