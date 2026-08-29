const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

function strategyResponse(mode) {
  const rows = {
    hybrid: {
      gates: 4,
      cost: 86.0,
      coverage: 1,
      missing: [],
      selected: ['res-mainboard-donor', 'res-display-controlled', 'res-keyboard-donor', 'res-battery-new', 'res-cooling-donor', 'res-shell-generated'],
      reason: 'Hybrid strategy covers the target by retaining evidenced donor islands and procuring the power gap.',
    },
    constrained: {
      gates: 6,
      cost: 59.0,
      coverage: 0.875,
      missing: ['power'],
      selected: ['res-mainboard-donor', 'res-display-raw', 'res-keyboard-donor', 'res-cooling-donor', 'res-shell-generated'],
      reason: 'Constrained strategy retains donor hardware but remains blocked on a safe power resource.',
    },
    open_procurement: {
      gates: 2,
      cost: 344.0,
      coverage: 1,
      missing: [],
      selected: ['res-mainboard-documented', 'res-display-documented', 'res-keyboard-donor', 'res-battery-new', 'res-pd-module', 'res-cooling-donor', 'res-shell-generated'],
      reason: 'Open procurement covers the target with documented modules and fewer evidence gaps.',
    },
  }[mode];

  return {
    resource_strategy: {
      schema_version: 'resource_strategy.v1',
      strategy_mode: mode,
      coverage: {
        covered_capabilities: ['x86_compute', 'display_or_ui', 'switch_or_button', 'storage', 'network_interface', 'fan_or_pump', 'enclosure_candidate'],
        missing_capabilities: rows.missing,
        coverage_score: rows.coverage,
      },
      build_readiness: {
        status: rows.missing.length ? 'blocked_missing_resources' : 'prototype_after_evidence',
        reason: rows.reason,
        open_gate_count: rows.gates,
        blocked_count: 1,
      },
      selected_resources: rows.selected.map((resource_id) => ({ resource_id, name: resource_id })),
      blocked_resources: [{ resource_id: 'res-battery-old', name: 'Unknown old lithium pack' }],
      procurement_plan: {
        items: mode === 'constrained' ? [{ resource_id: 'res-battery-new' }] : [{ resource_id: 'planner-procurement' }],
        estimated_cost_usd: rows.cost,
      },
    },
    metadata: { strategy_mode: mode },
  };
}

test('constructor consumes live resource_strategy.v1 projections without weakening authority', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.route('**/api/proxy/resource/strategy', async (route) => {
    const request = route.request();
    const body = JSON.parse(request.postData() || '{}');
    const mode = body.strategy_mode || 'hybrid';
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(strategyResponse(mode)) });
  });

  await page.goto(`${APP_URL}/workbench`);

  await expect(page.getByText('live planner', { exact: true })).toBeVisible();
  await expect(page.getByText('resource_strategy.v1', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('100% capability coverage', { exact: true })).toBeVisible();
  await expect(page.getByText('Hybrid strategy covers the target by retaining evidenced donor islands and procuring the power gap.', { exact: true }).first()).toBeVisible();

  const spatialProjection = page.getByTestId('candidate-spatial-projection');
  await expect(spatialProjection).toContainText('balanced');
  await expect(spatialProjection).toContainText('live');
  await expect(spatialProjection).toContainText('1 gaps');

  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await expect(page.getByRole('button', { name: /Donor x86 mainboard.*planner selected/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Donor display \+ validated controller.*planner selected/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Unknown old lithium pack/i })).not.toContainText('planner selected');

  // Constrained planning materially changes the machine: raw LCD is held and power becomes explicit gaps.
  await page.getByRole('button', { name: /Maximum reuse/ }).click();
  await expect(page.getByText('87.5% capability coverage', { exact: true })).toBeVisible();
  await expect(page.getByText('Missing: power', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Raw donor LCD panel.*planner selected/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Unknown old lithium pack/i })).not.toContainText('planner selected');
  await expect(spatialProjection).toContainText('max-reuse');
  await expect(spatialProjection).toContainText('1 held');
  await expect(spatialProjection).toContainText('2 gaps');
  await page.waitForTimeout(650);
  const constrainedCanvas = await page.locator('canvas').first().screenshot();

  // Open procurement substitutes documented compute/display geometry and closes the projected resource gaps.
  await page.getByRole('button', { name: /Lowest integration risk/ }).click();
  await expect(page.getByText('Open procurement covers the target with documented modules and fewer evidence gaps.', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Documented modular x86 board.*planner selected/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Documented portable display.*planner selected/i })).toBeVisible();
  await expect(spatialProjection).toContainText('low-risk');
  await expect(spatialProjection).toContainText('5 substitute');
  await expect(spatialProjection).toContainText('0 gaps');
  await page.waitForTimeout(650);
  const lowRiskCanvas = await page.locator('canvas').first().screenshot();
  expect(lowRiskCanvas.equals(constrainedCanvas)).toBeFalsy();
  await page.screenshot({ path: testInfo.outputPath('machine-constructor-live-planner.png') });

  // Proposal acceptance remains a working-design decision even under a live planner projection.
  await page.getByRole('button', { name: 'Accept proposal Use documented portable display to working candidate' }).click();
  await expect(page.getByText('accepted', { exact: true })).toBeVisible();
  await expect(page.getByText(/working design only/)).toBeVisible();
});
