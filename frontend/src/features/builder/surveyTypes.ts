import type { SurveyType } from '../../api/client';
import { icons } from '../../components/ui';

export const surveyTypes: {
  type: SurveyType;
  title: string;
  useWhen: string;
  detail: string;
  action: string;
  icon: string;
}[] = [
  {
    type: 'thumbs', title: 'Thumbs rating',
    useWhen: 'you want a quick read on one newsletter, article or announcement.',
    detail: 'One tap: Not for me, Good, Loved it. Results: % positive and % loved it.',
    action: 'Choose thumbs', icon: 'M7 10v12M15 6l-1 4h6l-3 12H3V10h4l5-8c2 0 3 2 3 4z',
  },
  {
    type: 'nps', title: 'NPS survey (0–10)',
    useWhen: 'you want to know how likely members, customers or employees are to recommend you.',
    detail: 'Promoters 9–10, passives 7–8, detractors 0–6. Score −100 to +100.',
    action: 'Choose NPS', icon: icons.chart,
  },
  {
    type: 'csat', title: 'CSAT survey (1–5)',
    useWhen: 'you want to know how satisfied people were with a course, event or service just now.',
    detail: 'Score = % of 4–5 answers, plus the average.',
    action: 'Choose CSAT', icon: 'M12 3l3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z',
  },
  {
    type: 'custom', title: 'Start from scratch',
    useWhen: 'no template fits and you want to write your own questions.',
    detail: 'Short and long answers, multiple choice, checkboxes, dropdowns and rating scales.',
    action: 'Build your own', icon: icons.edit,
  },
];
