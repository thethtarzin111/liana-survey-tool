import { expect, test } from '@playwright/test';

// Smoke test: the whole stack is up and the frontend reaches the API.
// Grow this into the main flow: create survey → answer → see results.

test('front page loads and greets the demo user through the API', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome, Anna' })).toBeVisible();
  await expect(page.getByText('Anna Virtanen · Example Members Association')).toBeVisible();
});

test('sidebar links open their pages', async ({ page }) => {
  await page.goto('/');
  for (const name of ['Surveys', 'Results', 'Responses', 'Contact requests', 'Templates']) {
    await page.getByRole('link', { name, exact: true }).click();
    await expect(page.getByRole('heading', { level: 1, name })).toBeVisible();
  }
});

test('API readiness check passes (database reachable)', async ({ request }) => {
  const res = await request.get('http://localhost:8000/health/ready');
  expect(res.ok()).toBeTruthy();
});
