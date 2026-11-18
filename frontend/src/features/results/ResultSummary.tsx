import { type SurveyResult } from '../../api/client';
import { Card } from '../../components/ui';

export function ResultSummary({ result }: { result: SurveyResult }) {
  const count = (values: number[]) => result.split.filter((item) => values.includes(item.value)).reduce((sum, item) => sum + item.count, 0);
  const total = result.split.reduce((sum, item) => sum + item.count, 0);
  const percent = (value: number) => total ? Math.round(value / total * 100) : 0;
  const groups = result.type === 'nps'
    ? [{label:'Detractors',count:count([0,1,2,3,4,5,6])},{label:'Passives',count:count([7,8])},{label:'Promoters',count:count([9,10])}]
    : result.type === 'csat'
      ? [{label:'Unsatisfied',count:count([1,2])},{label:'Neutral',count:count([3])},{label:'Satisfied',count:count([4,5])}]
      : [{label:'Not for me',count:count([0])},{label:'Good',count:count([1])},{label:'Loved it',count:count([2])}];
  const big = result.headline?.score.match(/[+−-]?\d+%?/)?.[0] ?? '—';
  const secondary = result.type === 'csat'
    ? total ? (result.split.reduce((sum,item)=>sum+item.value*item.count,0)/total).toFixed(1) : '—'
    : `${percent(groups[2].count)}%`;
  return <>
    <div className="result-metrics">
      <Card padded><span>{result.type === 'nps' ? 'NPS' : result.type === 'csat' ? 'Satisfied (4–5)' : 'Positive (Good + Loved it)'}</span><strong>{big}</strong><small>{result.type === 'nps' ? 'scale −100 to +100' : 'of readers who answered'}</small></Card>
      <Card padded><span>Answers</span><strong>{result.answers}</strong><small>{result.segment === 'all' ? 'All segments' : `Segment: ${result.segment}`}</small></Card>
      <Card padded><span>{result.type === 'nps' ? 'Promoters' : result.type === 'csat' ? 'Average' : 'Loved it'}</span><strong>{secondary}</strong><small>{result.type === 'csat' ? 'out of 5' : result.type === 'nps' ? `vs ${percent(groups[0].count)}% detractors` : `${groups[2].count} readers`}</small></Card>
    </div>
    <Card padded className="answer-split" aria-label="Answer split">
      <h2 className="visually-hidden">Answer split</h2>
      <div className="sentiment-bar" role="img" aria-label={groups.map(group=>`${group.label}: ${percent(group.count)}%`).join(', ')}>{groups.map((group,index)=><span key={group.label} className={`sentiment-${index}`} style={{flex:group.count}}>{group.count > 0 ? `${percent(group.count)}%` : ''}</span>)}</div>
      <ul>{groups.map((group,index)=><li key={group.label}><i className={`sentiment-${index}`} aria-hidden="true"/><strong>{group.label}</strong><span>{percent(group.count)}% · {group.count} answers</span></li>)}</ul>
    </Card>
  </>;
}
