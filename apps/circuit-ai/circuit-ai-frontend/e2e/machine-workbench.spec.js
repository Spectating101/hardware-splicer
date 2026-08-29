const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('machine workbench keeps spatial selection, authority, and evidence context coherent', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/workbench`);

  await expect(page.getByRole('heading', { name: 'DECK-001', level: 1 })).toBeVisible();
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

  // The assembly is a real spatial inspection surface: frame, x-ray, and engineering views are operable.
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

  // Spatial focus gives the 3D scene the whole workstation while preserving state-backed HUD context.
  const enterSpatial = page.getByRole('button', { name: 'Enter immersive spatial mode' });
  await enterSpatial.click();
  await expect(page.getByRole('button', { name: 'Exit immersive spatial mode' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('Machine tree', { exact: true })).toHaveCount(0);
  await expect(page.getByText('live spatial model', { exact: true })).toBeVisible();
  await expect(page.getByText('Spatial focus', { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('machine-workbench-immersive.png') });
  await page.getByRole('button', { name: 'Exit immersive spatial mode' }).click();
  await expect(page.getByText('Machine tree', { exact: true })).toBeVisible();

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

  // Power selection exposes the physical-authority blocker and inherits child evidence.
  await page.getByRole('button', { name: /^Power/ }).click();
  await expect(page.getByText('Physical authority', { exact: true })).toBeVisible();
  await expect(page.getByText('BLOCKED', { exact: true }).last()).toBeVisible();
  await expect(page.getByText('PD profiles', { exact: true })).toBeVisible();
  await expect(page.getByText('Power envelope required', { exact: true })).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath('machine-workbench-constraints.png') });

  await page.getByRole('button', { name: 'Authority', exact: true }).click();
  await expect(page.getByText('authority lens', { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('machine-workbench-assembly.png') });

  // Existing PCB renderer remains the specialized drill-down, but fixture truth stays explicit.
  await page.getByRole('button', { name: 'Compute PCB', exact: true }).click();
  await expect(page.getByText(/Representative x86 board fixture in the existing HS PCB renderer/)).toBeVisible();
  await expect(page.getByText(/Geometry remains synthetic until donor identity and measurements close/)).toBeVisible();
  await expect(page.locator('canvas').first()).toBeVisible();
  await expect(page.getByText('Donor x86 mainboard', { exact: true }).last()).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath('machine-workbench-pcb.png') });
});