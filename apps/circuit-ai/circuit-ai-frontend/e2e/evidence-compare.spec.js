const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('semantic revision compare keeps candidate artifact and authority boundary visible', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/engineering/evidence/compare`);

  await expect(page.getByText('Hardware Splicer', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Compare', exact: true })).toBeVisible();
  await expect(page.getByLabel('Base revision')).toHaveValue('5');
  await expect(page.getByLabel('Candidate revision')).toHaveValue('6');
  await expect(page.getByText('No automatic merge', { exact: true })).toBeVisible();

  await expect(page.getByText('Semantic delta', { exact: true })).toBeVisible();
  await expect(page.getByText('Needs review', { exact: true })).toBeVisible();
  await expect(page.getByText('Resolved', { exact: true })).toBeVisible();
  await expect(page.getByText('Changed', { exact: true })).toBeVisible();

  await expect(page.getByText(/1.8 V DUT interface is not protected from 3.3 V controller/).first()).toBeVisible();
  await expect(page.getByText(/Controller identity and source manual are now bound/)).toBeVisible();
  await expect(page.getByText(/Candidate adds the translated DUT interface boundary/)).toBeVisible();

  await expect(page.getByText('Candidate artifact', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Schematic', exact: true })).toBeVisible();
  await expect(page.locator('kicanvas-embed')).toHaveCount(1);

  await expect(page.getByText('Opened blocker', { exact: true }).last()).toBeVisible();
  await expect(page.getByText('dut-datasheet-r1', { exact: true })).toBeVisible();
  await expect(page.getByText('fixture-controller-manual-r1', { exact: true })).toBeVisible();
  await expect(page.getByText(/review evidence, not merge authority/i)).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath('evidence-compare.png'), fullPage: true });

  await expect(page.getByRole('button', { name: /Merge|Accept|Authorize|Fabricate|Power on/i })).toHaveCount(0);
  await expect(page.getByRole('link', { name: /Back to project review/ })).toHaveAttribute('href', /engineering\/evidence/);
});