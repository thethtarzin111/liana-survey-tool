import { expect, test } from '@playwright/test';

// The survey link page (#105) of two seeded, live surveys. "May newsletter" is a
// thumbs survey: the thumbs question, its reasons ("What stood out?") and a text
// question, all on one page. "Student services survey" has four required questions,
// three on the first page and one on the second.
// Nothing is submitted, so the demo data stays as it is.
const LINK = 'http://localhost:8000/r/demo-may-newsletter-0211?ch=link';
const PAGED_LINK = 'http://localhost:8000/r/demo-student-services-0214?ch=link';

test('the progress bar counts the questions shown and answered (#8)', async ({ page }) => {
  await page.goto(LINK);
  const progress = page.getByRole('progressbar', { name: 'Progress' });
  // Thumbs reasons are asked only after "Not for me": two questions at first.
  await expect(progress).toHaveAttribute('aria-valuetext', '0 of 2 answered');

  await page.getByRole('radio', { name: 'Good' }).check();
  await expect(progress).toHaveAttribute('aria-valuetext', '1 of 2 answered');
  await expect(progress).toHaveAttribute('aria-valuenow', '50');

  await page.getByRole('radio', { name: 'Not for me' }).check();
  await expect(progress).toHaveAttribute('aria-valuetext', '1 of 3 answered');
  // Three questions fit on one page: no Next, and Submit is shown.
  await expect(page.getByRole('button', { name: 'Next' })).toBeHidden();
  await expect(page.getByRole('button', { name: 'Submit' })).toBeVisible();
  await page.getByRole('checkbox', { name: 'Too long' }).check();
  await page.getByRole('textbox', { name: /Anything you would change/ }).fill('Shorter, please');
  await expect(progress).toHaveAttribute('aria-valuetext', '3 of 3 answered');
  await expect(progress).toHaveAttribute('aria-valuenow', '100');
});

test('several questions per page with Next and Previous, keeping answers (#176)', async ({ page }) => {
  await page.goto(PAGED_LINK);
  const next = page.getByRole('button', { name: 'Next' });
  const previous = page.getByRole('button', { name: 'Previous' });
  const submit = page.getByRole('button', { name: 'Submit' });
  const services = page.getByRole('group', { name: 'Which services have you used?' });
  const ease = page.getByRole('group', { name: 'How easy was it to get help?' });
  const campus = page.getByRole('combobox', { name: 'Which campus are you on?' });
  const improve = page.getByRole('textbox', { name: 'How could we improve student services?' });

  await expect(page.getByText('Page 1 of 2')).toBeVisible();
  await expect(services).toBeVisible();
  await expect(ease).toBeVisible();
  await expect(campus).toBeVisible();
  await expect(improve).toBeHidden();
  await expect(previous).toBeHidden();
  await expect(submit).toBeHidden();

  // Required questions on the page are answered before moving on.
  await services.getByRole('checkbox', { name: 'Counselling' }).check();
  await next.click();
  await expect(page.getByRole('alert')).toHaveText('Please answer every question that is not marked optional.');
  await expect(page.getByText('Page 1 of 2')).toBeVisible();

  await ease.getByRole('radio', { name: /^4/ }).check();
  await campus.selectOption('North');
  await expect(page.getByRole('alert')).toBeHidden();
  await next.click();
  await expect(page.getByText('Page 2 of 2')).toBeVisible();
  await expect(improve).toBeVisible();
  await expect(services).toBeHidden();
  await expect(next).toBeHidden();
  await expect(submit).toBeVisible();

  // Going back keeps the answers.
  await previous.click();
  await expect(page.getByText('Page 1 of 2')).toBeVisible();
  await expect(services.getByRole('checkbox', { name: 'Counselling' })).toBeChecked();
  await expect(ease.getByRole('radio', { name: /^4/ })).toBeChecked();
  await expect(campus).toHaveValue('North');
  await expect(previous).toBeHidden();
});
