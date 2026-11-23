import type { SurveyStatus } from '../../api/client';

/** The save button's texts. A published survey stays published when saved, so it is not called a draft. */
export function saveTexts(status: SurveyStatus) {
  return status === 'draft'
    ? { button: 'Save as draft', done: 'Saved as draft', failed: 'We couldn’t save your draft. Please try again.' }
    : { button: 'Save changes', done: 'Changes saved', failed: 'We couldn’t save your changes. Please try again.' };
}
