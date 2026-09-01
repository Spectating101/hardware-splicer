const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('product landing presents the reuse-first thesis and enters the mission workflow', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(APP_URL);

  await expect(page.getByRole('heading', { name: /Build useful machines/i })).toBeVisible();
  await expect(page.getByText('Inventory → Goal → Candidates → Resolve → Verify → Build', { exact: true })).toBeVisible();
  await expect(page.getByText(/Owned · salvaged · procurable · designed/i)).toBeVisible();
  await expect(page.getByText(/AI proposes · evidence constrains/i)).toBeVisible();

  const workbenchLink = page.getByRole('link', { name: /Open engineering workbench/i }).first();
  await expect(workbenchLink).toHaveAttribute('href', '/workbench');

  await page.getByRole('link', { name: /Start with hardware/i }).first().click();
  await expect(page).toHaveURL(/\/workbench\/mission$/);
  await expect(page.getByRole('heading', { name: 'Turn available hardware into a defensible build.' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Reuse mission stages' })).toBeVisible();
  await expect(page.getByText('Inventory', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Build', { exact: true }).first()).toBeVisible();
});
