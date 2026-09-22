const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('verification keeps deterministic results on the artifact and physical authority separate', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/engineering/evidence/verify`);

  await expect(page.getByText('Verification', { exact: true })).toBeVisible();
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Revision-bound design artifact/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Engineering sources/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Unresolved engineering blockers/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Physical correctness/ })).toBeVisible();

  await expect(page.getByRole('button', { name: 'Schematic', exact: true })).toBeVisible();
  await expect(page.locator('kicanvas-embed')).toHaveCount(1);

  await page.getByRole('button', { name: /Unresolved engineering blockers/ }).click();
  await expect(page.getByText(/remain blocked/).last()).toBeVisible();
  await expect(page.getByText(/blocks downstream confidence/)).toBeVisible();

  await expect(page.getByText(/FAB\s*CLOSED/)).toBeVisible();
  await expect(page.getByText(/POWER\s*CLOSED/)).toBeVisible();
  await expect(page.getByText(/RELEASE\s*CLOSED/)).toBeVisible();
  await expect(page.getByRole('link', { name: /Open physical bring-up/ })).toHaveAttribute('href', /engineering\/evidence\/bringup/);

  await expect(page.getByRole('button', { name: /Accept|Authorize|Fabricate|Power on/i })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('evidence-verify.png'), fullPage: true });
});

test('bring-up defaults to the PCB and keeps measurements distinct from authority', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/engineering/evidence/bringup`);

  await expect(page.getByText('Physical bring-up', { exact: true })).toBeVisible();
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /1\. Identity & assembly/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /2\. Cold checks/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /3\. Controlled power/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /4\. Functional test/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /5\. Release decision/ })).toBeVisible();

  const pcbTab = page.getByRole('button', { name: 'PCB', exact: true });
  await expect(pcbTab).toBeVisible();
  await expect(pcbTab).toHaveClass(/border-stone-900/);
  const pcbViewer = page.locator('kicanvas-embed');
  await expect(pcbViewer).toHaveCount(1);
  await expect(pcbViewer).toHaveAttribute('zoom', 'objects');

  await expect(page.getByText(/Power-on blocked/)).toBeVisible();
  await expect(page.getByText(/No physical measurement record is attached/)).toBeVisible();

  await page.getByRole('button', { name: /2\. Cold checks/ }).click();
  await expect(page.getByText(/no real measurement captured/).first()).toBeVisible();

  await expect(page.getByRole('button', { name: /Accept|Authorize|Fabricate|Power on/i })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('evidence-bringup.png'), fullPage: true });
});