const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test.setTimeout(75_000);

test('machine constructor keeps resources, candidates, proposals, spatial truth, and inspection coherent', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/workbench`);

  // Constructor is the primary surface: target + resources + candidate + proposals around the machine.
  await expect(page.getByRole('heading', { name: 'Portable Linux workstation', level: 1 })).toBeVisible();
  await expect(page.getByText('Constructor', { exact: true })).toBeVisible();
  await expect(page.getByText('Target contract projection', { exact: true })).toBeVisible();
  await expect(page.getByText('Proposal queue', { exact: true })).toBeVisible();
  await expect(page.getByText('Architecture candidates', { exact: true })).toBeVisible();
  await expect(page.getByText(/Build blocked · 3 gates/)).toBeVisible();
  await expect(page.locator('canvas').first()).toBeVisible();
  await expect(page.getByLabel(/Open Hardware Splicer/)).toHaveCount(0);

  // Standalone browser CI has no Circuit-AI backend: wait for the explicit honest fallback, not elapsed time.
  await expect(page.getByText('planner fixture', { exact: true })).toBeVisible();
  const spatialProjection = page.getByTestId('candidate-spatial-projection');
  await expect(spatialProjection).toContainText('balanced');
  await expect(spatialProjection).toContainText('fixture');
  const balancedCanvas = await page.locator('canvas').first().screenshot();

  // Changing objective changes both the architecture metadata and the actual WebGL composition.
  await page.getByRole('button', { name: /Lowest integration risk/ }).click();
  await expect(page.getByText(/Build blocked · 1 gate/)).toBeVisible();
  await expect(spatialProjection).toContainText('low-risk');
  await expect(spatialProjection).toContainText('5 substitute');
  await expect(spatialProjection).toContainText('0 gaps');
  await page.waitForTimeout(650);
  const lowRiskCanvas = await page.locator('canvas').first().screenshot();
  expect(lowRiskCanvas.equals(balancedCanvas)).toBeFalsy();

  await expect(page.getByRole('button', { name: 'Inspect proposal Use documented portable display' })).toBeVisible();
  await page.getByRole('button', { name: 'Accept proposal Use documented portable display to working candidate' }).click();
  await expect(page.getByText('accepted', { exact: true })).toBeVisible();
  await expect(page.getByText(/working design only/)).toBeVisible();

  // Resource selection maps back into the same spatial machine model.
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await expect(page.getByText('Unknown old lithium pack', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Donor display \+ validated controller/ }).click();
  await expect(page.getByText(/selected Donor display assembly/i)).toBeVisible();

  // The Jarvis-style command surface also drives constructor state.
  await page.getByRole('button', { name: 'Open spatial command console' }).click();
  const commandInput = page.getByRole('textbox', { name: 'Spatial command input' });
  await commandInput.fill('candidate max reuse');
  await commandInput.press('Enter');
  await expect(page.getByText('Maximum reuse is now the working architecture candidate. Authority gates are unchanged.', { exact: true })).toBeVisible();
  await expect(page.getByText(/Build blocked · 5 gates/)).toBeVisible();
  await expect(spatialProjection).toContainText('max-reuse');
  await expect(spatialProjection).toContainText('1 held');
  await commandInput.fill('show blockers');
  await commandInput.press('Enter');
  await expect(page.getByText('Blocking and unresolved paths surfaced across the machine.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close spatial command console' }).click();

  await page.screenshot({ path: testInfo.outputPath('machine-workbench-constructor.png') });

  // Inspection remains a sibling mode over the same canonical machine truth.
  await page.getByRole('button', { name: 'Inspect', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'DECK-001', level: 1 })).toBeVisible();
  await expect(page.getByText('Machine tree', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: /Donor display assembly/ }).click();
  await expect(page.getByText('Donor display assembly', { exact: true }).last()).toBeVisible();
  await expect(page.getByText('REUSE_PENDING', { exact: true })).toBeVisible();
  await expect(page.getByText('connector pinout', { exact: true })).toBeVisible();
  await expect(page.getByText('backlight power', { exact: true })).toBeVisible();

  await expect(page.getByRole('button', { name: 'Frame selection in 3D' })).toBeVisible();
  const xray = page.getByRole('button', { name: 'X-ray shell' });
  await xray.click();
  await expect(xray).toHaveAttribute('aria-pressed', 'true');
  await xray.click();
  await expect(xray).toHaveAttribute('aria-pressed', 'false');
  const topView = page.getByRole('button', { name: 'Top view' });
  await topView.click();
  await expect(topView).toHaveAttribute('aria-pressed', 'true');
  const isoView = page.getByRole('button', { name: 'Isometric view' });
  await isoView.click();
  await expect(isoView).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Frame selection in 3D' }).click();

  await page.getByRole('button', { name: 'Enter immersive spatial mode' }).click();
  await expect(page.getByRole('button', { name: 'Exit immersive spatial mode' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('Machine tree', { exact: true })).toHaveCount(0);
  await expect(page.getByText('live spatial model', { exact: true })).toBeVisible();
  await expect(page.getByText('Spatial focus', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Frame whole machine' }).click();
  await page.waitForTimeout(450);
  await page.screenshot({ path: testInfo.outputPath('machine-workbench-immersive.png') });
  await page.getByRole('button', { name: 'Exit immersive spatial mode' }).click();
  await expect(page.getByText('Machine tree', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: /Donor display assembly/ }).click();
  await page.getByRole('button', { name: 'Interfaces', exact: true }).first().click();
  await expect(page.getByText('interfaces lens', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Provenance', exact: true }).click();
  await expect(page.getByText('provenance lens', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Constraints', exact: true }).first().click();
  await expect(page.getByText('constraints lens', { exact: true }).first()).toBeVisible();

  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await expect(page.getByText('Display identity required', { exact: true })).toBeVisible();
  await expect(page.getByText(/Do not infer a raw panel pinout/)).toBeVisible();

  await page.getByRole('button', { name: /^Power/ }).click();
  await expect(page.getByText('Physical authority', { exact: true })).toBeVisible();
  await expect(page.getByText('BLOCKED', { exact: true }).last()).toBeVisible();
  await expect(page.getByText('PD profiles', { exact: true })).toBeVisible();
  await expect(page.getByText('Power envelope required', { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('machine-workbench-constraints.png') });

  await page.getByRole('button', { name: 'Authority', exact: true }).click();
  await expect(page.getByText('authority lens', { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('machine-workbench-assembly.png') });

  await page.getByRole('button', { name: 'Compute PCB', exact: true }).click();
  await expect(page.getByText(/Representative x86 board fixture in the existing HS PCB renderer/)).toBeVisible();
  await expect(page.getByText(/Geometry remains synthetic until donor identity and measurements close/)).toBeVisible();
  await expect(page.locator('canvas').first()).toBeVisible();
  await expect(page.getByText('Donor x86 mainboard', { exact: true }).last()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('machine-workbench-pcb.png') });
});