const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('public-renderer workbench keeps canonical evidence and blocker identity across views', async ({ page }) => {
  await page.goto(`${APP_URL}/engineering/visual`);

  await expect(page.getByRole('heading', { name: 'Visual Engineering Workbench' })).toBeVisible();
  await expect(page.getByText('Hardware Splicer moat layer')).toBeVisible();
  await expect(page.getByText('Viewers grant no authority')).toBeVisible();
  await expect(page.getByText('Revision 6', { exact: true }).first()).toBeVisible();

  await expect(page.getByText('USB fixture controller', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Unresolved translation', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('32-pin DUT socket', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Current-limited 1.8 V rail', { exact: true }).first()).toBeVisible();

  await page.getByText('Unresolved translation', { exact: true }).first().click();
  await expect(page.getByText('Contextual JARVIS inspector')).toBeVisible();
  await expect(page.getByText('dut-datasheet-r1', { exact: true })).toBeVisible();
  await expect(page.getByText('fixture-controller-manual-r1', { exact: true })).toBeVisible();
  await expect(page.getByText(/1.8 V DUT interface is not protected from 3.3 V controller/)).toBeVisible();
  await expect(page.getByText('Selected canonical ID:')).toBeVisible();
  await expect(page.getByText('level-translation', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: /KiCad adapter-ready/ }).click();
  await expect(page.getByRole('heading', { name: 'KiCanvas' })).toBeVisible();
  await expect(page.getByText('Never owned', { exact: true })).toBeVisible();
  await expect(page.getByText('No matching renderable artifact is registered in this project revision.')).toBeVisible();
  await expect(page.getByText('Unresolved translation', { exact: true }).last()).toBeVisible();

  await page.getByRole('button', { name: /Proposal adapter-ready/ }).click();
  await expect(page.getByRole('heading', { name: 'tscircuit / Circuit JSON' })).toBeVisible();
  await expect(page.getByText(/Conversion to KiCad requires an accepted deterministic action/)).toBeVisible();
  await expect(page.getByText('Authority effect')).toBeVisible();
  await expect(page.getByText('None', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: /System active/ }).click();
  await expect(page.getByText('Unresolved translation', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('level-translation', { exact: true })).toBeVisible();
});
