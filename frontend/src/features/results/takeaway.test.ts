import type { OverviewQuestion, SurveyOverview } from '../../api/client';
import { takeaway } from './takeaway';

const rating = (counts: number[], prompt = 'the information'): OverviewQuestion => ({
  id: 'r', kind: 'rating', prompt, required: false, answers: counts.reduce((a, b) => a + b, 0),
  options: counts.map((count, i) => ({ label: String(i + 1), count })), average: null,
});
const text: OverviewQuestion = { id: 't', kind: 'text', prompt: 'Why?', required: false, answers: 3, options: [], average: null };
const survey = (questions: OverviewQuestion[]) => ({ type: 'custom', questions }) as SurveyOverview;

describe('takeaway', () => {
  it('says most respondents rated 4–5 when at least half did', () => {
    expect(takeaway(survey([text, rating([1, 1, 5, 9, 14])]))).toBe('Most respondents rated the information 4–5 (77%).');
  });
  it('calls the ratings mixed below half', () => {
    expect(takeaway(survey([rating([4, 4, 3, 5, 4])]))).toBe('Ratings for the information are mixed: 45% gave 4–5.');
  });
  it('is null without a rating question or without answers', () => {
    expect(takeaway(survey([text]))).toBeNull();
    expect(takeaway(survey([rating([0, 0, 0, 0, 0])]))).toBeNull();
  });
});
