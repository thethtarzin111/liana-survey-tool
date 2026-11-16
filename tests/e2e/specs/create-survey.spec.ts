import { expect, test } from '@playwright/test';

test('choose a type with the keyboard, save a draft, and reopen it', async ({ page }) => {
  await page.goto('/surveys/new');
  const card = page.getByRole('button', { name: /^NPS survey/ });
  await expect(card).toContainText('Use this when');
  await card.focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/surveys\/[0-9a-f-]{36}$/);
  await expect(page.getByRole('heading', { name: 'Build your survey' })).toBeVisible();
  await expect(page.getByLabel(/^Survey title/)).toHaveValue('Untitled survey');
  await page.getByLabel(/^Survey title/).fill('Member survey');
  await page.getByLabel('Description (optional)').fill("Members' view of 2026");
  await page.getByRole('button', { name: 'Save as draft' }).click();
  await expect(page.getByText('Saved as draft')).toBeVisible();
  await page.reload();
  await expect(page.getByLabel(/^Survey title/)).toHaveValue('Member survey');
  await expect(page.getByLabel('Description (optional)')).toHaveValue("Members' view of 2026");
});

test('save errors leave the picker usable and a retry creates the draft', async ({ page }) => {
  await page.route('**/api/v1/surveys', (route) => route.fulfill({ status: 503 }), { times: 1 });
  await page.goto('/surveys/new');
  await page.getByRole('button', { name: /^Thumbs rating/ }).click();
  await expect(page.getByRole('alert')).toContainText('save your draft');
  await expect(page).toHaveURL(/\/surveys\/new$/);
  await page.getByRole('button', { name: /^Thumbs rating/ }).click();
  await expect(page).toHaveURL(/\/surveys\/[0-9a-f-]{36}$/);
  await expect(page.getByLabel(/^Survey title/)).toHaveValue('Untitled survey');
});

test('type cards stack on a phone without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/surveys/new');
  const cards = page.getByRole('region', { name: 'Survey types' }).getByRole('button');
  await expect(cards).toHaveCount(4);
  const first = (await cards.nth(0).boundingBox())!;
  const second = (await cards.nth(1).boundingBox())!;
  expect(second.y).toBeGreaterThanOrEqual(first.y + first.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
