const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test.setTimeout(75_000);

test('reuse mission turns strategy choices into canonical workbench state', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto(`${APP_URL}/workbench/mission`);

  await expect(page.getByRole('heading', { name: 'Turn available hardware into a defensible build.', level: 1 })).toBeVisible();
  await expect(page.getByText('Portable Linux workstation', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Reuse mission stages')).toContainText('Inventory');
  await expect(page.getByLabel('Reuse mission stages')).toContainText('Build');

  const maxReuse = page.getByRole('button', { name: /Maximum reuse/ });
  await maxReuse.click();
  await expect(maxReuse).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Resolve 5 blocking gates' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Build package' })).toBeDisabled();
  await page.screenshot({ path: testInfo.outputPath('reuse-mission-overview.png') });

  await page.getByRole('button', { name: 'Review available hardware' }).click();
  await expect(page).toHaveURL(/\/workbench\?stage=inventory&candidate=max-reuse$/);
  await expect(page.getByRole('heading', { name: 'Portable Linux workstation', level: 1 })).toBeVisible();
  await expect(page.getByText(/Build blocked · 5 gates/)).toBeVisible();
  await expect(page.getByText('Unknown old lithium pack', { exact: true })).toBeVisible();

  await page.goto(`${APP_URL}/workbench/mission`);
  const lowRisk = page.getByRole('button', { name: /Lowest integration risk/ });
  await lowRisk.click();
  await expect(lowRisk).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Open engineering verification' }).click();
  await expect(page).toHaveURL(/\/workbench\?stage=verify&candidate=low-risk$/);
  await expect(page.getByRole('heading', { name: 'DECK-001', level: 1 })).toBeVisible();
  await expect(page.getByText('Machine tree', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Verification', exact: true })).toBeVisible();
});
