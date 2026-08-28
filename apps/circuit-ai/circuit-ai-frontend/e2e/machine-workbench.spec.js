const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('machine workbench keeps spatial selection, authority, and evidence context coherent', async ({ page }, testInfo) => {
  await page.goto(`${APP_URL}/workbench`);

  await expect(page.getByRole('heading', { name: 'DECK-001' })).toBeVisible();
  await expect(page.getByText('Machine tree', { exact: true })).toBeVisible();
  await expect(page.getByText(/Build blocked · 3 gates/)).toBeVisible();
  await expect(page.locator('canvas').first()).toBeVisible();

  // The global launcher must not cover the machine workspace.
  await expect(page.getByLabel(/Open Hardware Splicer/)).toHaveCount(0);

  // Tree selection and inspector resolve the same canonical machine entity.
  await page.getByRole('button', { name: /Donor display assembly/ }).click();
  await expect(page.getByText('Donor display assembly', { exact: true }).last()).toBeVisible();
  await expect(page.getByText('REUSE_PENDING', { exact: true })).toBeVisible();
  await expect(page.getByText('connector pinout', { exact: true })).toBeVisible();
  await expect(page.getByText('backlight power', { exact: true })).toBeVisible();

  // Semantic lenses are operable without changing the underlying machine truth.
  await page.getByRole('button', { name: 'Interfaces', exact: true }).first().click();
  await expect(page.getByText('interfaces lens', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Provenance', exact: true }).click();
  await expect(page.getByText('provenance lens', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Constraints', exact: true }).first().click();
  await expect(page.getByText('constraints lens', { exact: true })).toBeVisible();

  // Evidence tray follows current selection and preserves the fail-closed display state.
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await expect(page.getByText('Display identity required', { exact: true })).toBeVisible();
  await expect(page.getByText(/Do not infer a raw panel pinout/)).toBeVisible();

  // Power selection exposes the physical-authority blocker rather than hiding it behind geometry.
  await page.getByRole('button', { name: /^Power/ }).click();
  await expect(page.getByText('Physical authority', { exact: true })).toBeVisible();
  await expect(page.getByText('BLOCKED', { exact: true }).last()).toBeVisible();
  await expect(page.getByText('PD profiles', { exact: true })).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath('machine-workbench-assembly.png'), fullPage: true });

  // Existing PCB rendering remains a specialized drill-down inside the machine workspace.
  await page.getByRole('button', { name: 'Compute PCB', exact: true }).click();
  await expect(page.getByText(/existing HS PCB renderer embedded inside the machine workbench/)).toBeVisible();
  await expect(page.locator('canvas').first()).toBeVisible();
  await expect(page.getByText('Donor x86 mainboard', { exact: true }).last()).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath('machine-workbench-pcb.png'), fullPage: true });
});
