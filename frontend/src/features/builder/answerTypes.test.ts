import type { Question } from '../../api/client';
import { NPS_PROMPT, changesForType, newOptionText } from './answerTypes';

const base: Question = { id: 'q1', survey_id: 's1', position: 1, kind: 'single_choice', prompt: '', options: ['Option 1'], required: false };

test('new options are numbered past the ones already taken', () => {
  expect(newOptionText('single_choice', ['Option 1'])).toBe('Option 2');
  expect(newOptionText('dropdown', ['Option 1', 'Option 3'])).toBe('Option 4');
  expect(newOptionText('multiple_choice', ['Yes', 'option 3'])).toBe('Option 4');
  expect(newOptionText('reasons', ['Price'])).toBe('New reason');
  expect(newOptionText('reasons', ['Price', 'New reason'])).toBe('New reason 2');
});

test('switching to NPS fills in the standard question only when there is none', () => {
  expect(changesForType(base, 'nps')).toEqual({ kind: 'nps', prompt: NPS_PROMPT });
  expect(changesForType({ ...base, prompt: 'Recommend us?' }, 'nps')).toEqual({ kind: 'nps' });
});

test('switching to Reason bubbles replaces untouched placeholders with common reasons', () => {
  const reasons = ['Price', 'Quality', 'Customer service', 'Something else'];
  expect(changesForType({ ...base, options: ['Option 1', 'Option 2'] }, 'reasons').options).toEqual(reasons);
  expect(changesForType({ ...base, kind: 'text', options: [] }, 'reasons').options).toEqual(reasons);
  expect(changesForType({ ...base, options: ['Events', 'Option 2'] }, 'reasons')).toEqual({ kind: 'reasons' });
});

test('choice types keep their options, or start with Option 1 coming from other types', () => {
  expect(changesForType({ ...base, options: ['Yes', 'No'] }, 'dropdown')).toEqual({ kind: 'dropdown' });
  expect(changesForType({ ...base, kind: 'rating', options: [] }, 'multiple_choice')).toEqual({
    kind: 'multiple_choice',
    options: ['Option 1'],
  });
  expect(changesForType(base, 'long_text')).toEqual({ kind: 'long_text' });
});
