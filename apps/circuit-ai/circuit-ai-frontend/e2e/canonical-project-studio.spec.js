const fs = require('node:fs');
const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const PACKAGE_ID = 'engineering-package-r00000008-outsiderfixture';

test('new user can resume a project and finish the visible JARVIS workflow in one Studio', async ({ page }, testInfo) => {
  await page.goto(`${APP_URL}/engineering/studio`);
  await expect(page.getByRole('heading', { name: 'Project Studio' })).toBeVisible();
  await expect(page.getByText('What are you trying to build, verify, repair, or understand?')).toBeVisible();
  await expect(page.getByText('Brief', { exact: true })).toBeVisible();
  await expect(page.getByText('Evidence', { exact: true })).toBeVisible();
  await expect(page.getByText('Candidate', { exact: true })).toBeVisible();
  await expect(page.getByText('JARVIS', { exact: true })).toBeVisible();
  await expect(page.getByText('Package', { exact: true })).toBeVisible();

  const projectCard = page.getByRole('button', { name: /Outsider DUT fixture/ });
  await expect(projectCard).toBeVisible();
  await projectCard.click();

  await expect(page.getByText('Revision 6', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('2 registered sources', { exact: true })).toBeVisible();
  await expect(page.getByText('Direct controller DUT adapter')).toBeVisible();
  await expect(page.getByText('Compile the DUT validation adapter')).toBeVisible();
  await expect(page.getByText(/1.8 V DUT interface is not protected from 3.3 V controller/)).toBeVisible();
  await expect(page.getByText('Fabrication')).toBeVisible();
  await expect(page.getByText('closed', { exact: true }).first()).toBeVisible();

  await page.getByPlaceholder('What is still unsupported? Which action should we review next? Is this ready for fabrication?').fill(
    'Is this fixture ready for fabrication?',
  );
  await page.getByRole('button', { name: 'Ask from revision 6' }).click();

  await expect(page.getByText('Revision 7', { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/The fixture is not pre-fabrication ready/)).toBeVisible();
  await expect(page.getByText('Prepare fixture pre-fabrication verification')).toBeVisible();
  await expect(page.getByText(/No powered-off high-impedance translator is proven/)).toBeVisible();
  await expect(page.getByText('2 persisted turns').or(page.getByText('1 persisted turn'))).toBeVisible();

  const repairButton = page.getByRole('button', { name: 'Propose repair' });
  await expect(repairButton).toBeVisible();
  await repairButton.click();

  await expect(page.getByText('Revision 8', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Default-off translated DUT adapter')).toBeVisible();
  await expect(page.getByText('Add protected translation')).toBeVisible();
  await expect(page.getByText('Repair created as a separate successor. The failed result remains immutable.')).toBeVisible();

  await page.getByRole('button', { name: 'Export revision 8' }).click();
  await expect(page.getByText('Revision 9', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Created a deterministic package from source revision 8.')).toBeVisible();
  await expect(page.getByText('Source revision 8', { exact: true })).toBeVisible();
  await expect(page.getByText(PACKAGE_ID)).toBeVisible();
  await expect(page.getByText(`ZIP SHA-256: ${'3'.repeat(64)}`)).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Verified ZIP' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(`${PACKAGE_ID}.zip`);
  const downloadPath = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(downloadPath);
  const bytes = fs.readFileSync(downloadPath);
  expect(bytes.length).toBeGreaterThan(100);
  expect(bytes.subarray(0, 2).toString('ascii')).toBe('PK');

  await expect(page.getByText('AI proposals, software previews, conversation, and package export do not open physical gates.')).toBeVisible();
});
