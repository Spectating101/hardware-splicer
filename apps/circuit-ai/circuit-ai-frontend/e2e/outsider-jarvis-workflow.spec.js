const fs = require('node:fs');
const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const PROJECT_ID = 'outsider-fixture';
const SESSION_ID = 'outsider-session';

async function loadJarvisWorkspace(page) {
  await page.goto(`${APP_URL}/engineering/jarvis`);
  await expect(page.getByRole('heading', { name: 'JARVIS Console' })).toBeVisible();
  await page.locator('input[placeholder="project-id"]').fill(PROJECT_ID);
  await page.locator('input[placeholder="ai-session-id"]').fill(SESSION_ID);
  await page.getByRole('button', { name: 'Load project session' }).click();
  await expect(page.getByText('Revision 6', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('2 sources', { exact: true })).toBeVisible();
  await expect(page.getByText('JARVIS is guidance, not project truth.')).toBeVisible();
}

test('outsider completes grounded question, repair review, and verified package download', async ({ page }, testInfo) => {
  await loadJarvisWorkspace(page);

  await page.getByPlaceholder('What failed, what is still unknown, and what should we do next?').fill(
    'Is this fixture ready for fabrication?',
  );
  await page.getByRole('button', { name: 'Ask from revision 6' }).click();

  await expect(page.getByText('Revision 7', { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/The fixture is not pre-fabrication ready/)).toBeVisible();
  await expect(page.getByText(/tool_result · action-failed-compose/)).toBeVisible();
  await expect(page.getByText(/No powered-off high-impedance translator is proven/)).toBeVisible();
  await expect(page.getByText('Prepare fixture pre-fabrication verification')).toBeVisible();
  await expect(page.getByText('Awaiting human review')).toBeVisible();

  await page.getByRole('link', { name: 'Review in AI Studio' }).click();
  await expect(page).toHaveURL(/\/engineering\/ai-studio$/);
  await expect(page.getByRole('heading', { name: 'AI Project Studio' })).toBeVisible();

  await page.locator('input[placeholder="project-id"]').fill(PROJECT_ID);
  await page.getByRole('button', { name: 'Load project' }).click();
  await expect(page.getByText('Revision 7', { exact: true }).first()).toBeVisible();
  await page.locator('input[placeholder="ai-session-id"]').fill(SESSION_ID);
  await page.getByRole('button', { name: 'Load session' }).click();

  await expect(page.getByText('Compile the DUT validation adapter')).toBeVisible();
  await expect(page.getByText(/1.8 V DUT interface is not protected from 3.3 V controller/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Propose bounded repair' })).toBeVisible();
  await page.getByRole('button', { name: 'Propose bounded repair' }).click();

  await expect(page.getByText('Revision 8', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Repair successor summary' })).toBeVisible();
  await expect(page.getByText('Default-off translated DUT adapter')).toBeVisible();
  await expect(page.getByText('Failed action: action-failed-compose')).toBeVisible();
  await expect(page.getByText('Iteration: 1')).toBeVisible();
  await expect(page.getByText('Add protected translation')).toBeVisible();

  await page.getByRole('link', { name: 'Packages', exact: true }).click();
  await expect(page).toHaveURL(/\/engineering\/packages$/);
  await expect(page.getByRole('heading', { name: 'Engineering Packages' })).toBeVisible();

  await page.locator('input[placeholder="project-id"]').fill(PROJECT_ID);
  await page.getByRole('button', { name: 'Load project' }).click();
  await expect(page.getByText('Current revision 8', { exact: true })).toBeVisible();
  await expect(page.getByText('0 package records', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Export revision 8' }).click();

  await expect(page.getByText('Current revision 9', { exact: true })).toBeVisible();
  await expect(page.getByText('Created deterministic package from source revision 8.')).toBeVisible();
  await expect(page.getByText('Source revision 8', { exact: true })).toBeVisible();
  await expect(page.getByText('15 files', { exact: true })).toBeVisible();
  await expect(page.getByText('engineering-package-r00000008-outsiderfixture')).toBeVisible();
  await expect(page.getByText('1'.repeat(64), { exact: true })).toBeVisible();
  await expect(page.getByText('2'.repeat(64), { exact: true })).toBeVisible();
  await expect(page.getByText('3'.repeat(64), { exact: true })).toBeVisible();
  await expect(page.getByText('Raw source bytes: excluded', { exact: true })).toBeVisible();
  await expect(page.getByText('Physical authority unchanged', { exact: true })).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Verified ZIP' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('engineering-package-r00000008-outsiderfixture.zip');
  const downloadPath = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(downloadPath);
  const bytes = fs.readFileSync(downloadPath);
  expect(bytes.length).toBeGreaterThan(100);
  expect(bytes.subarray(0, 2).toString('ascii')).toBe('PK');

  await expect(page.getByText('A package records project state; it does not authorize fabrication')).toBeVisible();
});
