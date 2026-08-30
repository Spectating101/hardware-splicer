const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

function strategyResponse(mode) {
  return {
    resource_strategy: {
      schema_version: 'resource_strategy.v1',
      strategy_mode: mode,
      coverage: {
        covered_capabilities: ['x86_compute', 'display_or_ui'],
        missing_capabilities: [],
        coverage_score: 1,
      },
      build_readiness: {
        status: 'prototype_after_evidence',
        reason: 'Exact-BREP browser fixture keeps the two placed donor resources selected.',
        open_gate_count: 2,
        blocked_count: 0,
      },
      selected_resources: [
        { resource_id: 'res-mainboard-donor', name: 'Donor x86 mainboard' },
        { resource_id: 'res-display-controlled', name: 'Donor display + validated controller' },
      ],
      blocked_resources: [],
      procurement_plan: { items: [], estimated_cost_usd: 0 },
    },
    metadata: { strategy_mode: mode },
  };
}

function geometryResponse(sourceId, modelId) {
  const display = sourceId.includes('display');
  const size = display ? [305, 195, 12] : [210, 130, 18];
  const pointCount = display ? 12 : 8;
  return {
    ok: true,
    mechanical_geometry: {
      schema_version: 'hardware_splicer.mechanical_geometry_report.v1',
      project_id: 'deck-001',
      models: [{
        schema_version: 'hardware_splicer.step_geometry.v1',
        source_id: sourceId,
        model_id: modelId,
        content_hash: `sha256:${(display ? 'b' : 'a').repeat(64)}`,
        byte_count: 512,
        file_schema: ['AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'],
        products: [display ? 'Donor Display Assembly' : 'Donor Mainboard'],
        units: 'mm',
        entity_count: 42,
        cartesian_point_count: pointCount,
        bounding_box: {
          minimum: [0, 0, 0],
          maximum: size,
          size,
          point_count: pointCount,
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
  const placement = body.placements[0];
  const model = body.geometry.models.find((row) => row.model_id === placement.model_id);
  const minimum = model.bounding_box.minimum.map((value, index) => value + placement.translation_mm[index]);
  const maximum = model.bounding_box.maximum.map((value, index) => value + placement.translation_mm[index]);
  return {
    ok: true,
    clearance_boxes: [{
      object_id: placement.object_id,
      frame_id: placement.target_frame,
      minimum_mm: minimum,
      maximum_mm: maximum,
      source_model_id: placement.model_id,
      state: 'declared_placement',
      metadata: {
        placement_id: placement.placement_id,
        placement_authority: 'declared',
        translation_mm: placement.translation_mm,
        rotation_deg_xyz: placement.rotation_deg_xyz,
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

const mainboardStep = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(210.,130.,18.));\nENDSEC;\nEND-ISO-10303-21;\n";
const displayStep = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(305.,195.,12.));\nENDSEC;\nEND-ISO-10303-21;\n";

test('workbench exact BREP pair clearance stays distinct from AABB and reproduces fail-25 pass-15', async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1600, height: 1000 });
  const exactRequirements = [];

  await page.route('**/api/proxy/resource/strategy', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(strategyResponse(body.strategy_mode || 'hybrid')),
    });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/parse', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    const source = body.sources[0];
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(geometryResponse(source.source_id, source.model_id)),
    });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/place', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(placementResponse(body)),
    });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/interference', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    expect(body.first_source.content).toContain('ISO-10303-21');
    expect(body.second_source.content).toContain('ISO-10303-21');
    expect(body.first_placement.authority).toBe('declared');
    expect(body.second_placement.authority).toBe('declared');
    const required = Number(body.minimum_clearance_mm);
    exactRequirements.push(required);
    const passed = required <= 20;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        brep_interference: {
          schema_version: 'hardware_splicer.brep_pair_interference.v1',
          status: 'clear',
          required_evidence: [],
          metadata: { aabb_fallback_used: false },
        },
        kernel_available: true,
        exact_pair_interference_evaluated: true,
        exact_solid_interference: false,
        minimum_distance_mm: 20,
        intersection_volume_mm3: 0,
        exact_minimum_clearance_evaluated: true,
        minimum_clearance_requirement_mm: required,
        minimum_clearance_passed: passed,
        minimum_clearance_message: passed
          ? `Exact BREP minimum distance 20.000 mm meets the ${required.toFixed(3)} mm requirement.`
          : `Exact BREP minimum distance 20.000 mm is below the ${required.toFixed(3)} mm requirement.`,
        aabb_fallback_used: false,
        full_brep_collision: false,
        connector_mating_verified: false,
        cable_routing_verified: false,
        service_access_verified: false,
        structural_analysis: false,
        physical_measurement: false,
        automatic_execution: false,
        physical_action: false,
        manufacturing_authorized: false,
        fabrication_authorized: false,
        power_on_authorized: false,
        motion_authorized: false,
        release_authorized: false,
      }),
    });
  });

  await page.goto(`${APP_URL}/workbench`);
  await expect(page.getByText('live planner', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Resources', exact: true }).click();

  const mainboard = page.getByRole('button', { name: /Donor x86 mainboard.*planner selected/i });
  await mainboard.click();
  await page.getByLabel('Attach STEP geometry for Donor x86 mainboard').setInputFiles({
    name: 'donor-mainboard.step',
    mimeType: 'model/step',
    buffer: Buffer.from(mainboardStep),
  });
  await expect(page.getByTestId('step-geometry-import')).toContainText('STEP envelope attached: 210 × 130 × 18 mm');
  await page.getByLabel('Placement translation X mm for Donor x86 mainboard').fill('40');
  await page.getByLabel('Placement translation Y mm for Donor x86 mainboard').fill('-65');
  await page.getByLabel('Placement translation Z mm for Donor x86 mainboard').fill('10');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Placed in assembly: T [40, -65, 10] mm');

  const display = page.getByRole('button', { name: /Donor display \+ validated controller.*planner selected/i });
  await display.click();
  await page.getByLabel('Attach STEP geometry for Donor display + validated controller').setInputFiles({
    name: 'donor-display.step',
    mimeType: 'model/step',
    buffer: Buffer.from(displayStep),
  });
  await expect(page.getByTestId('step-geometry-import')).toContainText('STEP envelope attached: 305 × 195 × 12 mm');
  await page.getByLabel('Placement translation X mm for Donor display + validated controller').fill('270');
  await page.getByLabel('Placement translation Y mm for Donor display + validated controller').fill('-65');
  await page.getByLabel('Placement translation Z mm for Donor display + validated controller').fill('10');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();

  const exactChecker = page.getByTestId('exact-brep-clearance-checker');
  await expect(exactChecker).toBeVisible();
  await expect(exactChecker).toContainText('Both canonical STEP uploads are available in this browser session');
  await expect(exactChecker).toContainText('CadQuery/OCCT · no AABB fallback');

  await page.getByLabel('Minimum declared clearance mm').fill('25');
  await page.getByRole('button', { name: 'Check exact BREP clearance' }).click();
  await expect(exactChecker).toContainText('Exact BREP minimum distance 20.000 mm is below the 25.000 mm requirement.');
  await expect(exactChecker).toContainText('NO SOLID OVERLAP · 20.000 mm minimum BREP distance.');
  await expect(exactChecker).toContainText('Exact means this placed STEP solid pair only.');

  await page.getByLabel('Minimum declared clearance mm').fill('15');
  await page.getByRole('button', { name: 'Check exact BREP clearance' }).click();
  await expect(exactChecker).toContainText('Exact BREP minimum distance 20.000 mm meets the 15.000 mm requirement.');
  await expect(exactChecker).toContainText('NO SOLID OVERLAP · 20.000 mm minimum BREP distance.');

  expect(exactRequirements).toEqual([25, 15]);
});