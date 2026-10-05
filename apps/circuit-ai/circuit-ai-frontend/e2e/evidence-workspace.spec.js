const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('project review keeps artifact, findings, evidence, and authority in one read-only workspace', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/engineering/evidence`);

  await expect(page.getByText('Hardware Splicer', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();

  await expect(page.getByText('Design', { exact: true })).toBeVisible();
  const fabricationChip = page.getByText('Fabrication', { exact: true }).locator('..');
  await expect(fabricationChip).toContainText('Blocked');
  await expect(page.getByText('Power-on', { exact: true })).toBeVisible();

  await expect(page.getByRole('button', { name: /Project/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Findings/ }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /History/ })).toBeVisible();

  await expect(page.getByRole('button', { name: 'Schematic', exact: true })).toBeVisible();
  await expect(page.locator('kicanvas-embed')).toHaveCount(1);

  const controllerObject = page.getByRole('button', { name: /USB fixture controller/ });
  const translationObject = page.getByRole('button', { name: /Unresolved translation/ });
  const socketObject = page.getByRole('button', { name: /32-pin DUT socket/ });
  await expect(controllerObject).toBeVisible();
  await expect(translationObject).toBeVisible();
  await expect(socketObject).toBeVisible();

  await translationObject.click();
  await expect(page.getByRole('heading', { name: 'Unresolved translation' })).toBeVisible();
  await expect(page).toHaveURL(/object=level-translation/);

  await page.getByRole('button', { name: /Findings/ }).last().click();
  await expect(page.getByText(/1.8 V DUT interface is not protected from 3.3 V controller/).last()).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath('evidence-workspace.png'), fullPage: true });

  await page.getByRole('button', { name: /Evidence/ }).click();
  await expect(page.getByText('dut-datasheet-r1', { exact: true })).toBeVisible();
  await expect(page.getByText('fixture-controller-manual-r1', { exact: true })).toBeVisible();

  await expect(page.getByText(/FAB\s*CLOSED/)).toBeVisible();
  await expect(page.getByText(/POWER\s*CLOSED/)).toBeVisible();
  await expect(page.getByText(/RELEASE\s*CLOSED/)).toBeVisible();

  await expect(page.locator('a[href^="/engineering/evidence/compare"]')).toHaveCount(1);
  await expect(page.locator('a[href^="/engineering/evidence/verify"]')).toHaveCount(1);
  await expect(page.locator('a[href^="/engineering/evidence/bringup"]')).toHaveCount(1);

  await expect(page.getByRole('button', { name: /Accept|Authorize|Fabricate|Power on/i })).toHaveCount(0);
});
test('review states the next step, ties evidence to the claims it supports, and is keyboard-navigable', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/engineering/evidence`);

  const nextStep = page.getByTestId('next-step');
  await expect(nextStep).toContainText('Design is blocked');
  await expect(nextStep.getByRole('button', { name: /first/ })).toBeVisible();
  await expect(nextStep.getByRole('button', { name: /Authorize|Approve|Accept|Fabricate|Power on/i })).toHaveCount(0);

  await page.getByRole('button', { name: /^Evidence/ }).first().click();
  await expect(page.getByText('Cited by').first()).toBeVisible();

  await page.keyboard.press('j');
  await expect(page.locator('aside h2').first()).toHaveText('Unresolved translation');

  await page.keyboard.press('?');
  await expect(page.getByRole('dialog', { name: 'Keyboard shortcuts' })).toBeVisible();
  await page.keyboard.press('Escape');

  await page.keyboard.press('3');
  await expect(page).toHaveURL(/\/engineering\/evidence\/verify/);
});

test('findings say how they were established and the discussion layer never touches authority', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/engineering/evidence?project=outsider-fixture&object=level-translation`);

  await page.getByRole('button', { name: /^Findings/ }).first().click();
  // Object blockers the backend did not label must read as "not recorded", never as a check result.
  await expect(page.getByText('Provenance not recorded').first()).toBeVisible();

  await page.getByRole('button', { name: 'Project', exact: true }).first().click();
  await page.getByRole('button', { name: 'Threads', exact: true }).click();
  const panel = page.getByTestId('review-threads');
  await expect(panel).toContainText('Comments never change findings, evidence or authority.');
  await expect(panel.locator('section').first()).toBeVisible();

  const before = await panel.locator('section').count();
  await page.getByPlaceholder('Who is commenting').fill('E2E reviewer');
  await page.locator('#new-thread-body').fill('Does the translator default to disabled at power-up?');
  await page.getByRole('button', { name: 'Start thread' }).click();
  await expect(panel.locator('section')).toHaveCount(before + 1);

  // Discussion is not authority: the strip is unchanged.
  const authority = page.locator('aside').last();
  await expect(authority).toContainText(/FAB\s*CLOSED/);
  await expect(authority).toContainText(/POWER\s*CLOSED/);
  await expect(authority).toContainText(/RELEASE\s*CLOSED/);
});

test('comments can be pinned to a location on the artifact and follow the viewer', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/engineering/evidence?project=outsider-fixture&object=level-translation`);
  await page.getByRole('button', { name: 'Threads', exact: true }).click();
  const panel = page.getByTestId('review-threads');
  await expect(panel.locator('section').first()).toBeVisible();

  // The fixture ships one pinned thread.
  const pins = page.getByTestId('thread-pin');
  await expect(pins.first()).toBeVisible();
  const before = await pins.count();

  await page.getByRole('button', { name: 'Pin to artifact' }).click();
  const layer = page.getByTestId('pin-placement');
  await expect(layer).toBeVisible();
  const box = await layer.boundingBox();
  await page.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.35);
  await expect(panel).toContainText(/Pinned at -?\d+(\.\d+)?, -?\d+(\.\d+)? mm/);

  await page.getByPlaceholder('Who is commenting').fill('E2E pinner');
  await page.locator('#new-thread-body').fill('Pinned from the e2e run.');
  await page.getByRole('button', { name: 'Start thread' }).click();
  await expect(pins).toHaveCount(before + 1);

  // Esc leaves placement without creating anything.
  await page.getByRole('button', { name: 'Pin to artifact' }).click();
  await expect(page.getByTestId('pin-placement')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('pin-placement')).toHaveCount(0);
  await expect(pins).toHaveCount(before + 1);
});

test('an operator token marks a comment verified and a wrong token writes nothing', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/engineering/evidence?project=outsider-fixture&object=level-translation`);
  await page.evaluate(() => window.sessionStorage.clear());
  await page.reload();
  await page.getByRole('button', { name: 'Threads', exact: true }).click();
  const panel = page.getByTestId('review-threads');
  await expect(panel.locator('section').first()).toBeVisible();
  const before = await panel.locator('section').count();

  await page.getByText('Have an operator token?').click();
  await page.getByLabel('Operator token').fill('not-a-registered-token');
  await page.locator('#new-thread-body').fill('This must be refused.');
  await page.getByRole('button', { name: 'Start thread' }).click();
  await expect(panel.getByRole('alert')).toContainText(/not recognised|not recognized/i);
  await expect(panel.locator('section')).toHaveCount(before);

  await page.getByRole('button', { name: 'Remove' }).click();
  await page.getByText('Have an operator token?').click();
  await page.getByLabel('Operator token').fill('demo-operator-token');
  await page.locator('#new-thread-body').fill('Verified by the demo operator.');
  await page.getByRole('button', { name: 'Start thread' }).click();
  await expect(panel.locator('section')).toHaveCount(before + 1);
  await expect(panel.getByText('verified', { exact: true }).first()).toBeVisible();
  await expect(panel).toContainText('demo-operator');
});
