import { expect, test } from '@playwright/test';

// The survey link page (#105) of the seeded, live "May newsletter" thumbs survey.
// Nothing is submitted, so the demo data stays as it is.
const LINK = 'http://localhost:8000/r/demo-may-newsletter-0211?ch=link';

test('the progress bar counts the questions shown and answered (#8)', async ({ page }) => {
  await page.goto(LINK);
  const progress = page.getByRole('progressbar', { name: 'Progress' });
  // Thumbs reasons are asked only after "Not for me": two questions at first.
  await expect(progress).toHaveAttribute('aria-valuetext', '0 of 2 answered');
  await expect(page.getByRole('group', { name: 'What stood out?' })).toBeHidden();

  await page.getByRole('radio', { name: 'Good' }).check();
  await expect(progress).toHaveAttribute('aria-valuetext', '1 of 2 answered');
  await expect(progress).toHaveAttribute('aria-valuenow', '50');

  await page.getByRole('radio', { name: 'Not for me' }).check();
  await expect(page.getByRole('group', { name: 'What stood out?' })).toBeVisible();
  await expect(progress).toHaveAttribute('aria-valuetext', '1 of 3 answered');
  await page.getByRole('checkbox', { name: 'Too long' }).check();
  await page.getByRole('textbox', { name: /Anything you would change/ }).fill('Shorter, please');
  await expect(progress).toHaveAttribute('aria-valuetext', '3 of 3 answered');
  await expect(progress).toHaveAttribute('aria-valuenow', '100');
});
