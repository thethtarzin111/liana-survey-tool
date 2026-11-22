import type { SurveyListItem } from '../../api/client';

export function LatestSplit({ survey }: { survey: SurveyListItem }) {
  const counts = survey.answer_counts;
  if (!counts || survey.type === 'custom') return null;
  const groups = survey.type === 'nps' ? [[0,1,2,3,4,5,6],[7,8],[9,10]] : survey.type === 'csat' ? [[1,2],[3],[4,5]] : [[0],[1],[2]];
  const labels = survey.type === 'nps' ? ['Detractors','Passives','Promoters'] : survey.type === 'csat' ? ['Unsatisfied','Neutral','Satisfied'] : ['Not for me','Good','Loved it'];
  const values = groups.map(group=>group.reduce((sum,value)=>sum+(counts[String(value)] ?? 0),0));
  const total = values.reduce((sum,value)=>sum+value,0);
  return <div className="latest-split"><div className="latest-bar" role="img" aria-label={labels.map((label,index)=>`${label}: ${total ? Math.round(values[index]/total*100) : 0}%`).join(', ')}>{values.map((value,index)=><span key={index} className={`latest-tone-${index}`} style={{flex:value}} />)}</div><div className="latest-legend">{labels.map((label,index)=><span key={label}><i className={`latest-tone-${index}`} />{label} <strong>{total ? Math.round(values[index]/total*100) : 0}%</strong></span>)}</div></div>;
}
