const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('project review keeps artifact, findings, evidence, and authority in one read-only workspace', async ({ page }) => {
  await page.goto(`${APP_URL}/engineering/evidence`);

  await expect(page.getByText('Hardware Splicer', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();

  await expect(page.getByText('Design', { exact: true })).toBeVisible();
  const fabricationChip = page.getByText('Fabrication', { exact: true }).locator('..');
  await expect(fabricationChip).toContainText('Blocked');
  await expect(page.getByText('Power-on', { exact: true })).toBeVisible();

  await expect(page.getByRole('button', { name: /Project/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Findings/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /History/ })).toBeVisible();

  await expect(page.getByText('USB fixture controller', { exact: true })).toBeVisible();
  await expect(page.getByText('Unresolved translation', { exact: true })).toBeVisible();
  await expect(page.getByText('32-pin DUT socket', { exact: true })).toBeVisible();

  await page.getByText('Unresolved translation', { exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Unresolved translation' })).toBeVisible();
  await expect(page).toHaveURL(/object=level-translation/);

  await page.getByRole('button', { name: /Findings/ }).last().click();
  await expect(page.getByText(/1.8 V DUT interface is not protected from 3.3 V controller/)).toBeVisible();

  await page.getByRole('button', { name: /Evidence/ }).click();
  await expect(page.getByText('dut-datasheet-r1', { exact: true })).toBeVisible();
  await expect(page.getByText('fixture-controller-manual-r1', { exact: true })).toBeVisible();

  await expect(page.getByText('FAB', { exact: true })).toBeVisible();
  await expect(page.getByText('POWER', { exact: true })).toBeVisible();
  await expect(page.getByText('RELEASE', { exact: true })).toBeVisible();
  await expect(page.getByText('CLOSED', { exact: true })).toHaveCount(3);

  await expect(page.getByRole('link', { name: /Compare/ })).toHaveAttribute('href', /mode=decide/);
  await expect(page.getByRole('link', { name: /Bring-up/ })).toHaveAttribute('href', /mode=bringup/);

  await expect(page.getByRole('button', { name: /Accept|Authorize|Fabricate|Power on/i })).toHaveCount(0);
});
