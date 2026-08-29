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

function stepGeometryResponse(sourceId = 'donor-mainboard.step') {
  return {
    ok: true,
    mechanical_geometry: {
      schema_version: 'hardware_splicer.mechanical_geometry_report.v1',
      project_id: 'deck-001',
      models: [{
        schema_version: 'hardware_splicer.step_geometry.v1',
        source_id: sourceId,
        model_id: 'balanced-res-mainboard-donor',
        content_hash: `sha256:${'a'.repeat(64)}`,
        byte_count: 512,
        file_schema: ['AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'],
        products: ['Donor Mainboard'],
        units: 'mm',
        entity_count: 42,
        cartesian_point_count: 8,
        bounding_box: {
          minimum: [0, 0, 0],
          maximum: [210, 130, 18],
          size: [210, 130, 18],
          point_count: 8,
          units: 'mm',
        },
        authority: 'declared',
        unresolved: [],
        metadata: {
          full_brep_validation: false,
          collision_analysis: false,
          fabrication_authorized: false,
        },
      }],
      mounts: [],
      checks: [],
      status: 'candidate',
      required_evidence: [],
      metadata: {},
    },
    model_count: 1,
    blocking_check_count: 0,
    step_point_envelope_only: true,
    full_brep_collision: false,
    mass_properties_verified: false,
    automatic_execution: false,
    physical_action: false,
    manufacturing_authorized: false,
    fabrication_authorized: false,
    power_on_authorized: false,
    motion_authorized: false,
    release_authorized: false,
  };
}

test('constructor consumes live resource_strategy.v1 and bounded STEP evidence without weakening authority', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.route('**/api/proxy/resource/strategy', async (route) => {
    const request = route.request();
    const body = JSON.parse(request.postData() || '{}');
    const mode = body.strategy_mode || 'hybrid';
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(strategyResponse(mode)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/parse', async (route) => {
    const request = route.request();
    const body = JSON.parse(request.postData() || '{}');
    const sourceId = body.sources?.[0]?.source_id || 'donor-mainboard.step';
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(stepGeometryResponse(sourceId)) });
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
  const donorMainboard = page.getByRole('button', { name: /Donor x86 mainboard.*planner selected/i });
  await expect(donorMainboard).toBeVisible();
  await expect(page.getByRole('button', { name: /Donor display \+ validated controller.*planner selected/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Unknown old lithium pack/i })).not.toContainText('planner selected');

  // Real file input -> canonical mechanical parser contract -> exact resource envelope -> WebGL geometry delta.
  await donorMainboard.click();
  await expect(page.getByTestId('step-geometry-import')).toContainText('Spatial evidence · Donor x86 mainboard');
  await page.waitForTimeout(650);
  const fixtureMainboardCanvas = await page.locator('canvas').first().screenshot();
  await page.getByLabel('Attach STEP geometry for Donor x86 mainboard').setInputFiles({
    name: 'donor-mainboard.step',
    mimeType: 'model/step',
    buffer: Buffer.from("ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(210.,130.,18.));\nENDSEC;\nEND-ISO-10303-21;\n"),
  });
  await expect(page.getByTestId('step-geometry-import')).toContainText('STEP envelope attached: 210 × 130 × 18 mm · 8 points · DECLARED');
  await expect(donorMainboard).toContainText('STEP envelope');
  await expect(page.getByText('DECLARED STEP ENVELOPE', { exact: true })).toBeVisible();
  await page.waitForTimeout(650);
  const stepMainboardCanvas = await page.locator('canvas').first().screenshot();
  expect(stepMainboardCanvas.equals(fixtureMainboardCanvas)).toBeFalsy();

  // Constrained planning materially changes the machine; geometry evidence remains candidate/resource scoped.
  await page.getByRole('button', { name: /Maximum reuse/ }).click();
  await page.getByRole('button', { name: 'Target', exact: true }).click();
  await expect(page.getByText('88% capability coverage', { exact: true })).toBeVisible();
  await expect(page.getByText('Missing: power', { exact: true })).toBeVisible();
  await expect(spatialProjection).toContainText('max-reuse');
  await expect(spatialProjection).toContainText('1 held');
  await expect(spatialProjection).toContainText('2 gaps');
  await expect(page.getByText('DECLARED STEP ENVELOPE', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await expect(page.getByRole('button', { name: /Raw donor LCD panel.*planner selected/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Unknown old lithium pack/i })).not.toContainText('planner selected');
  await page.waitForTimeout(650);
  const constrainedCanvas = await page.locator('canvas').first().screenshot();

  // Open procurement substitutes documented compute/display geometry and closes the projected resource gaps.
  await page.getByRole('button', { name: /Lowest integration risk/ }).click();
  await page.getByRole('button', { name: 'Target', exact: true }).click();
  await expect(page.getByText('Open procurement covers the target with documented modules and fewer evidence gaps.', { exact: true }).first()).toBeVisible();
  await expect(spatialProjection).toContainText('low-risk');
  await expect(spatialProjection).toContainText('5 substitute');
  await expect(spatialProjection).toContainText('0 gaps');
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await expect(page.getByRole('button', { name: /Documented modular x86 board.*planner selected/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Documented portable display.*planner selected/i })).toBeVisible();
  await page.waitForTimeout(650);
  const lowRiskCanvas = await page.locator('canvas').first().screenshot();
  expect(lowRiskCanvas.equals(constrainedCanvas)).toBeFalsy();
  await page.screenshot({ path: testInfo.outputPath('machine-constructor-live-planner.png') });

  // Proposal acceptance remains a working-design decision even under a live planner projection.
  await page.getByRole('button', { name: 'Accept proposal Use documented portable display to working candidate' }).click();
  await expect(page.getByText('accepted', { exact: true })).toBeVisible();
  await expect(page.getByText(/working design only/)).toBeVisible();
});
