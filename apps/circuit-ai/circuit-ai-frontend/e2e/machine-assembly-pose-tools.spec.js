const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

const mainboardStep = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(210.,130.,18.));\nENDSEC;\nEND-ISO-10303-21;\n";

function strategyResponse(mode) {
  return {
    resource_strategy: {
      schema_version: 'resource_strategy.v1',
      strategy_mode: mode,
      coverage: {
        covered_capabilities: ['x86_compute', 'display_or_ui', 'switch_or_button', 'storage', 'network_interface', 'fan_or_pump', 'enclosure_candidate'],
        missing_capabilities: [],
        coverage_score: 1,
      },
      build_readiness: {
        status: 'prototype_after_evidence',
        reason: 'Pose-tool fixture keeps the candidate evidence-bound.',
        open_gate_count: 3,
        blocked_count: 0,
      },
      selected_resources: [
        'res-mainboard-donor',
        'res-display-controlled',
        'res-keyboard-donor',
        'res-battery-new',
        'res-cooling-donor',
        'res-shell-generated',
      ].map((resource_id) => ({ resource_id, name: resource_id })),
      blocked_resources: [],
      procurement_plan: { items: [], estimated_cost_usd: 0 },
    },
    metadata: { strategy_mode: mode },
  };
}

function geometryResponse(sourceId, modelId) {
  return {
    ok: true,
    mechanical_geometry: {
      schema_version: 'hardware_splicer.mechanical_geometry_report.v1',
      project_id: 'deck-001',
      models: [{
        schema_version: 'hardware_splicer.step_geometry.v1',
        source_id: sourceId,
        model_id: modelId,
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

function placementResponse(body) {
  const placement = body.placements?.[0] || {};
  const translation = placement.translation_mm || [0, 0, 0];
  return {
    ok: true,
    clearance_boxes: [{
      object_id: placement.object_id || 'cmp-mainboard',
      frame_id: placement.target_frame || 'assembly',
      minimum_mm: [0, 0, 0].map((value, index) => value + translation[index]),
      maximum_mm: [210, 130, 18].map((value, index) => value + translation[index]),
      source_model_id: placement.model_id,
      state: 'declared_placement',
      metadata: {
        placement_id: placement.placement_id,
        placement_authority: 'declared',
        translation_mm: translation,
        rotation_deg_xyz: placement.rotation_deg_xyz || [0, 0, 0],
        rotation_convention: 'Rz*Ry*Rx; canonical STEP XYZ',
        source_envelope_only: true,
        full_brep_collision: false,
        physical_measurement: false,
        fabrication_authorized: false,
      },
    }],
    placement_count: 1,
    declared_rigid_placement_only: true,
    aabb_only: true,
    full_brep_collision: false,
    physical_measurement: false,
    fabrication_authorized: false,
    automatic_execution: false,
    physical_action: false,
    manufacturing_authorized: false,
    power_on_authorized: false,
    motion_authorized: false,
    release_authorized: false,
  };
}

test('STEP-backed assembly pose tools edit canonical translation and rotation through the real placement contract', async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  const placementPayloads = [];

  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.route('**/api/proxy/resource/strategy', async (route) => {
    const body = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(strategyResponse(body.strategy_mode || 'hybrid')) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/parse', async (route) => {
    const body = route.request().postDataJSON();
    const source = body.sources?.[0] || {};
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(geometryResponse(source.source_id || 'donor-mainboard.step', source.model_id || 'donor-mainboard-model')) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/place', async (route) => {
    const body = route.request().postDataJSON();
    placementPayloads.push(body);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(placementResponse(body)) });
  });

  await page.goto(`${APP_URL}/workbench`);
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  const donorMainboard = page.getByRole('button', { name: /Donor x86 mainboard.*planner selected/i });
  await donorMainboard.click();
  await page.getByLabel('Attach STEP geometry for Donor x86 mainboard').setInputFiles({
    name: 'donor-mainboard.step',
    mimeType: 'model/step',
    buffer: Buffer.from(mainboardStep),
  });

  const toolbar = page.getByTestId('assembly-placement-toolbar');
  await expect(toolbar).toBeVisible();
  await expect(toolbar).toContainText('Assembly pose · Donor x86 mainboard');
  await expect(toolbar).toContainText('No declared pose yet');

  await toolbar.getByRole('button', { name: 'Move', exact: true }).click();
  await expect(toolbar.getByRole('button', { name: 'Move', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('assembly-pose-draft-label')).toContainText('DECLARED POSE DRAFT · MOVE');
  const precision = page.getByTestId('assembly-placement-precision-pad');
  await expect(precision).toBeVisible();
  await precision.getByLabel('Nudge move X positive 1mm').click();
  await precision.getByLabel('Nudge move X positive 1mm').click();
  await expect(page.getByTestId('assembly-pose-readout')).toContainText('T [2, 0, 0] mm');

  await toolbar.getByRole('button', { name: 'Apply pose' }).click();
  await expect.poll(() => placementPayloads.length).toBe(1);
  expect(placementPayloads[0].placements[0].translation_mm).toEqual([2, 0, 0]);
  expect(placementPayloads[0].placements[0].rotation_deg_xyz).toEqual([0, 0, 0]);
  expect(placementPayloads[0].placements[0].authority).toBe('declared');
  await expect(toolbar).toContainText('Declared pose committed');
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Placed in assembly: T [2, 0, 0] mm · R [0, 0, 0]° · DECLARED.');

  await toolbar.getByRole('button', { name: 'Rotate', exact: true }).click();
  await expect(page.getByTestId('assembly-pose-draft-label')).toContainText('DECLARED POSE DRAFT · ROTATE');
  await precision.getByRole('button', { name: '90°', exact: true }).click();
  await precision.getByLabel('Nudge rotate Z positive 90°').click();
  await expect(page.getByTestId('assembly-pose-readout')).toContainText('R [0, 0, 90]°');
  await toolbar.getByRole('button', { name: 'Apply pose' }).click();
  await expect.poll(() => placementPayloads.length).toBe(2);
  expect(placementPayloads[1].placements[0].translation_mm).toEqual([2, 0, 0]);
  expect(placementPayloads[1].placements[0].rotation_deg_xyz).toEqual([0, 0, 90]);

  await toolbar.getByRole('button', { name: 'Move', exact: true }).click();
  await precision.getByLabel('Nudge move Y positive 1mm').click();
  await expect(page.getByTestId('assembly-pose-readout')).toContainText('T [2, 1, 0] mm');
  await toolbar.getByRole('button', { name: 'Revert' }).click();
  await expect.poll(() => placementPayloads.length).toBe(2);
  await expect(toolbar).toContainText('Draft discarded; committed declared pose is unchanged.');
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Placed in assembly: T [2, 0, 0] mm · R [0, 0, 90]° · DECLARED.');

  await page.screenshot({ path: testInfo.outputPath('assembly-pose-tools.png') });
});
