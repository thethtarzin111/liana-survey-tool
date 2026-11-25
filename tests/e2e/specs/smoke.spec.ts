import { expect, test } from '@playwright/test';

// Smoke test: the whole stack is up and the frontend reaches the API.
// Grow this into the main flow: create survey → answer → see results.

test('front page loads the dashboard and the demo user through the API', async ({ page }) => {
  await page.goto('/');
  // Shown only after the surveys request succeeds.
  await expect(page.getByRole('heading', { name: 'Overall statistics' })).toBeVisible();
  const account = page.getByRole('button', { name: 'Account: Anna Virtanen' });
  await expect(account).toContainText('Example Members Association');
});

test('sidebar links open their pages', async ({ page }) => {
  await page.goto('/');
  for (const name of ['Surveys', 'Results', 'Templates']) {
    await page.getByRole('link', { name, exact: true }).click();
    await expect(page.getByRole('heading', { level: 1, name })).toBeVisible();
  }
});

// Responses is a tab of Results. The old /responses path redirects there.
test('/responses opens the Responses tab of Results', async ({ page }) => {
  await page.goto('/responses');
  await expect(page).toHaveURL(/\/results\?.*tab=responses/);
  await expect(page.getByRole('heading', { level: 1, name: 'Results' })).toBeVisible();

  // The tabs appear only when the demo database has surveys.
  const responsesTab = page.getByRole('tab', { name: /^Responses/ });
  const noSurveys = page.getByText('No surveys yet', { exact: true });
  await expect(responsesTab.or(noSurveys)).toBeVisible();
  if (await responsesTab.isVisible()) {
    await expect(responsesTab).toHaveAttribute('aria-selected', 'true');
  }
});

test('API readiness check passes (database reachable)', async ({ request }) => {
  const res = await request.get('http://localhost:8000/health/ready');
  expect(res.ok()).toBeTruthy();
});

// The API gateway is the only entry point and decides who the user is.
test('gateway ignores identity headers sent by the client', async ({ request }) => {
  const created = await request.post('http://localhost:8000/api/v1/surveys', {
    data: { type: 'nps', title: 'Gateway header test' },
    headers: { 'X-Tenant-Id': '00000000-0000-4000-8000-0000000000ff' },
  });
  expect(created.status()).toBe(201);
  const id = (await created.json()).id;

  // Created for the demo tenant, not the one in the forged header.
  const read = await request.get(`http://localhost:8000/api/v1/surveys/${id}`);
  expect(read.status()).toBe(200);
});

test('gateway routes each path to its service', async ({ request }) => {
  const me = await request.get('http://localhost:8000/api/v1/me');
  expect((await me.json()).name).toBe('Anna Virtanen');
  expect((await request.get('http://localhost:8000/health')).ok()).toBeTruthy();
  expect((await request.get('http://localhost:8000/nope')).status()).toBe(404);
  // Respondent service answers /r/ (no endpoints yet, so FastAPI's 404).
  expect((await request.get('http://localhost:8000/r/unknown')).status()).toBe(404);
});
