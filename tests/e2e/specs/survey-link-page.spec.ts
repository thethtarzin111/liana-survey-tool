import { expect, test } from '@playwright/test';

// The survey link page (#105) of the seeded, live "May newsletter" thumbs survey:
// the thumbs question, its reasons ("What stood out?") and a text question.
// Nothing is submitted, so the demo data stays as it is.
const LINK = 'http://localhost:8000/r/demo-may-newsletter-0211?ch=link';

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
  await page.getByRole('button', { name: 'Next' }).click();
  await page.getByRole('checkbox', { name: 'Too long' }).check();
  await page.getByRole('button', { name: 'Next' }).click();
  await page.getByRole('textbox', { name: /Anything you would change/ }).fill('Shorter, please');
  await expect(progress).toHaveAttribute('aria-valuetext', '3 of 3 answered');
  await expect(progress).toHaveAttribute('aria-valuenow', '100');
});

test('one question at a time with Next and Previous, keeping answers (#9)', async ({ page }) => {
  await page.goto(LINK);
  const next = page.getByRole('button', { name: 'Next' });
  const previous = page.getByRole('button', { name: 'Previous' });
  const submit = page.getByRole('button', { name: 'Submit' });
  await expect(page.getByText('Question 1 of 2')).toBeVisible();
  await expect(previous).toBeHidden();
  await expect(submit).toBeHidden();

  // Required questions are answered before moving on.
  await next.click();
  await expect(page.getByRole('alert')).toHaveText('Please answer this question.');
  await expect(page.getByText('Question 1 of 2')).toBeVisible();

  await page.getByRole('radio', { name: 'Not for me' }).check();
  await expect(page.getByRole('alert')).toBeHidden();
  await next.click();
  await expect(page.getByText('Question 2 of 3')).toBeVisible();
  await expect(page.getByRole('group', { name: 'What stood out?' })).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Good' })).toBeHidden();
  await page.getByRole('checkbox', { name: 'Too long' }).check();
  await next.click();
  await expect(page.getByText('Question 3 of 3')).toBeVisible();
  await expect(next).toBeHidden();
  await expect(submit).toBeVisible();

  // Going back keeps the answers.
  await previous.click();
  await expect(page.getByRole('checkbox', { name: 'Too long' })).toBeChecked();
  await previous.click();
  await expect(page.getByRole('radio', { name: 'Not for me' })).toBeChecked();
  await expect(previous).toBeHidden();
});
