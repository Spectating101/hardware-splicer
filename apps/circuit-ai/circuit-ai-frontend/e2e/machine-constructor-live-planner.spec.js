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

function stepGeometryResponse(sourceId, modelId) {
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
        byte_count: display ? 768 : 512,
        file_schema: ['AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'],
        products: [display ? 'Donor Display Assembly' : 'Donor Mainboard'],
        units: 'mm',
        entity_count: display ? 57 : 42,
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
  const placement = body.placements?.[0] || {};
  const model = (body.geometry?.models || []).find((row) => row.model_id === placement.model_id) || body.geometry?.models?.[0] || {};
  const box = model.bounding_box || { minimum: [0, 0, 0], maximum: [1, 1, 1] };
  const translation = placement.translation_mm || [0, 0, 0];
  const minimum = box.minimum.map((value, index) => value + translation[index]);
  const maximum = box.maximum.map((value, index) => value + translation[index]);
  return {
    ok: true,
    clearance_boxes: [{
      object_id: placement.object_id || 'component',
      frame_id: placement.target_frame || 'assembly',
      minimum_mm: minimum,
      maximum_mm: maximum,
      source_model_id: placement.model_id || model.model_id,
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

function accessEnvelopeResponse(body) {
  const parent = body.object_box || {};
  const access = body.access || {};
  const faceAxes = {
    '+x': [0, 1, 1, 2], '-x': [0, -1, 1, 2],
    '+y': [1, 1, 0, 2], '-y': [1, -1, 0, 2],
    '+z': [2, 1, 0, 1], '-z': [2, -1, 0, 1],
  };
  const [normalAxis, normalSign, uAxis, vAxis] = faceAxes[access.face || '+x'];
  const minimum = parent.minimum_mm || [0, 0, 0];
  const maximum = parent.maximum_mm || [1, 1, 1];
  const anchor = [0, 1, 2].map((index) => (minimum[index] + maximum[index]) / 2);
  anchor[normalAxis] = normalSign > 0 ? maximum[normalAxis] : minimum[normalAxis];
  anchor[uAxis] += Number(access.offset_u_mm || 0);
  anchor[vAxis] += Number(access.offset_v_mm || 0);
  const accessMinimum = [...anchor];
  const accessMaximum = [...anchor];
  accessMinimum[uAxis] = anchor[uAxis] - Number(access.width_mm) / 2;
  accessMaximum[uAxis] = anchor[uAxis] + Number(access.width_mm) / 2;
  accessMinimum[vAxis] = anchor[vAxis] - Number(access.height_mm) / 2;
  accessMaximum[vAxis] = anchor[vAxis] + Number(access.height_mm) / 2;
  if (normalSign > 0) {
    accessMinimum[normalAxis] = anchor[normalAxis];
    accessMaximum[normalAxis] = anchor[normalAxis] + Number(access.depth_mm);
  } else {
    accessMinimum[normalAxis] = anchor[normalAxis] - Number(access.depth_mm);
    accessMaximum[normalAxis] = anchor[normalAxis];
  }
  const outwardNormal = [0, 0, 0];
  outwardNormal[normalAxis] = normalSign;
  return {
    ok: true,
    access_box: {
      object_id: `access:${access.access_id}`,
      frame_id: access.frame_id || parent.frame_id || 'assembly',
      minimum_mm: accessMinimum,
      maximum_mm: accessMaximum,
      source_model_id: parent.source_model_id || null,
      state: 'declared_access_envelope',
      metadata: {
        schema_version: 'hardware_splicer.declared_interface_access.v1',
        access_id: access.access_id,
        interface_id: access.interface_id,
        parent_object_id: access.object_id,
        parent_placement_id: parent.metadata?.placement_id,
        access_authority: 'declared',
        face: access.face,
        anchor_point_mm: anchor,
        outward_normal: outwardNormal,
        width_mm: access.width_mm,
        height_mm: access.height_mm,
        depth_mm: access.depth_mm,
        offset_u_mm: access.offset_u_mm || 0,
        offset_v_mm: access.offset_v_mm || 0,
        aabb_only: true,
        cable_routing_verified: false,
        connector_mating_verified: false,
        service_access_verified: false,
        full_brep_collision: false,
        physical_measurement: false,
        fabrication_authorized: false,
      },
    },
    declared_interface_access_only: true,
    aabb_only: true,
    cable_routing_verified: false,
    connector_mating_verified: false,
    service_access_verified: false,
    full_brep_collision: false,
    physical_measurement: false,
    automatic_execution: false,
    physical_action: false,
    manufacturing_authorized: false,
    fabrication_authorized: false,
    power_on_authorized: false,
    motion_authorized: false,
    release_authorized: false,
  };
}

function fitResponse(body) {
  const [first, second] = body.clearance_boxes || [];
  const requirement = body.clearance_requirements?.[0] || { minimum_clearance_mm: 0 };
  const separations = [0, 1, 2].map((index) => Math.max(
    second.minimum_mm[index] - first.maximum_mm[index],
    first.minimum_mm[index] - second.maximum_mm[index],
    0,
  ));
  let clearance;
  if (separations.some((value) => value > 0)) {
    clearance = Math.sqrt(separations.reduce((sum, value) => sum + value * value, 0));
  } else {
    const overlaps = [0, 1, 2].map((index) => Math.min(first.maximum_mm[index], second.maximum_mm[index]) - Math.max(first.minimum_mm[index], second.minimum_mm[index]));
    clearance = overlaps.every((value) => value > 0) ? -Math.min(...overlaps) : 0;
  }
  const passed = clearance >= requirement.minimum_clearance_mm;
  const message = passed
    ? `AABB clearance ${clearance.toFixed(3)} mm meets the ${Number(requirement.minimum_clearance_mm).toFixed(3)} mm requirement.`
    : `AABB clearance ${clearance.toFixed(3)} mm is below the ${Number(requirement.minimum_clearance_mm).toFixed(3)} mm requirement.`;
  return {
    ok: true,
    mechanical_fit: {
      schema_version: 'hardware_splicer.mechanical_fit.v1',
      project_id: 'deck-001',
      geometry_report_schema: 'hardware_splicer.mechanical_geometry_report.v1',
      clearance_boxes: body.clearance_boxes,
      clearance_requirements: body.clearance_requirements,
      fastener_stacks: [],
      checks: [{
        check_id: requirement.requirement_id,
        category: 'aabb_clearance',
        status: passed ? 'pass' : 'fail',
        message,
        target_ids: [first.object_id, second.object_id],
        unresolved_fields: [],
        blocking: true,
        metadata: { clearance_mm: clearance, minimum_clearance_mm: requirement.minimum_clearance_mm, frame_id: first.frame_id, aabb_only: true },
      }],
      status: passed ? 'candidate' : 'blocked',
      required_evidence: passed ? [] : [{ check_id: requirement.requirement_id, category: 'aabb_clearance' }],
      metadata: { full_brep_collision: false },
    },
    blocking_check_count: passed ? 0 : 1,
    full_brep_collision: false,
    structural_analysis: false,
    thread_strength_verified: false,
    automatic_execution: false,
    physical_action: false,
    manufacturing_authorized: false,
    fabrication_authorized: false,
    power_on_authorized: false,
    motion_authorized: false,
    release_authorized: false,
  };
}

const mainboardStep = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(210.,130.,18.));\nENDSEC;\nEND-ISO-10303-21;\n";
const displayStep = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(305.,195.,12.));\nENDSEC;\nEND-ISO-10303-21;\n";

test('constructor consumes live resource strategy, spatial evidence dependencies, and bounded mechanical checks without weakening authority', async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.route('**/api/proxy/resource/strategy', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(strategyResponse(body.strategy_mode || 'hybrid')) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/parse', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    const source = body.sources?.[0] || {};
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(stepGeometryResponse(source.source_id || 'component.step', source.model_id || 'component-model')) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/place', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(placementResponse(body)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/interfaces/access-envelope', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(accessEnvelopeResponse(body)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/fit/check', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(fitResponse(body)) });
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
  const donorDisplay = page.getByRole('button', { name: /Donor display \+ validated controller.*planner selected/i });
  await expect(donorMainboard).toBeVisible();
  await expect(donorDisplay).toBeVisible();
  await expect(page.getByRole('button', { name: /Unknown old lithium pack/i })).not.toContainText('planner selected');

  // Resource fixture -> parsed STEP point envelope -> declared common-frame placement.
  await donorMainboard.click();
  await expect(page.getByTestId('step-geometry-import')).toContainText('Spatial evidence · Donor x86 mainboard');
  await page.waitForTimeout(650);
  const fixtureMainboardCanvas = await page.locator('canvas').first().screenshot();
  await page.getByLabel('Attach STEP geometry for Donor x86 mainboard').setInputFiles({ name: 'donor-mainboard.step', mimeType: 'model/step', buffer: Buffer.from(mainboardStep) });
  await expect(page.getByTestId('step-geometry-import')).toContainText('STEP envelope attached: 210 × 130 × 18 mm · 8 points · DECLARED');
  await expect(donorMainboard).toContainText('STEP envelope');
  await expect(page.getByText('DECLARED STEP ENVELOPE', { exact: true })).toBeVisible();
  await page.waitForTimeout(650);
  const stepMainboardCanvas = await page.locator('canvas').first().screenshot();
  expect(stepMainboardCanvas.equals(fixtureMainboardCanvas)).toBeFalsy();

  await expect(page.getByTestId('declared-placement-editor')).toBeVisible();
  await page.getByLabel('Placement translation X mm for Donor x86 mainboard').fill('40');
  await page.getByLabel('Placement translation Y mm for Donor x86 mainboard').fill('-65');
  await page.getByLabel('Placement translation Z mm for Donor x86 mainboard').fill('10');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Placed in assembly: T [40, -65, 10] mm · R [0, 0, 0]° · DECLARED.');
  await expect(page.getByText('DECLARED PLACED ENVELOPE', { exact: true })).toBeVisible();
  await page.waitForTimeout(650);
  const placedMainboardCanvas = await page.locator('canvas').first().screenshot();
  expect(placedMainboardCanvas.equals(stepMainboardCanvas)).toBeFalsy();

  // A second resource must start with its own transform controls, never the previous resource's values.
  await donorDisplay.click();
  await expect(page.getByTestId('step-geometry-import')).toContainText('Spatial evidence · Donor display + validated controller');
  await page.getByLabel('Attach STEP geometry for Donor display + validated controller').setInputFiles({ name: 'donor-display.step', mimeType: 'model/step', buffer: Buffer.from(displayStep) });
  await expect(page.getByTestId('step-geometry-import')).toContainText('STEP envelope attached: 305 × 195 × 12 mm · 12 points · DECLARED');
  await expect(page.getByLabel('Placement translation X mm for Donor display + validated controller')).toHaveValue('0');
  await expect(page.getByLabel('Placement translation Y mm for Donor display + validated controller')).toHaveValue('0');
  await expect(page.getByLabel('Placement translation Z mm for Donor display + validated controller')).toHaveValue('0');
  await page.getByLabel('Placement translation X mm for Donor display + validated controller').fill('270');
  await page.getByLabel('Placement translation Y mm for Donor display + validated controller').fill('-65');
  await page.getByLabel('Placement translation Z mm for Donor display + validated controller').fill('10');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Placed in assembly: T [270, -65, 10] mm · R [0, 0, 0]° · DECLARED.');

  // Two independently sourced/placed STEP envelopes share a declared assembly frame.
  // Their X envelopes are 20 mm apart. A 25 mm requirement fails; 15 mm passes.
  const clearanceChecker = page.getByTestId('declared-clearance-checker');
  await expect(clearanceChecker).toBeVisible();
  await expect(clearanceChecker).toContainText('same-frame AABB only');
  await page.getByLabel('Minimum declared clearance mm').fill('25');
  await page.getByRole('button', { name: 'Check AABB clearance' }).click();
  await expect(clearanceChecker).toContainText('AABB clearance 20.000 mm is below the 25.000 mm requirement.');
  await page.getByLabel('Minimum declared clearance mm').fill('15');
  await page.getByRole('button', { name: 'Check AABB clearance' }).click();
  await expect(clearanceChecker).toContainText('AABB clearance 20.000 mm meets the 15.000 mm requirement.');
  await expect(clearanceChecker).toContainText('does not establish BREP collision freedom');

  // Interface semantics now gain a bounded spatial keep-out only after placement.
  await donorMainboard.click();
  await expect(page.getByLabel('Placement translation X mm for Donor x86 mainboard')).toHaveValue('40');
  const accessEditor = page.getByTestId('declared-interface-access-editor');
  await expect(accessEditor).toBeVisible();
  await expect(page.getByLabel('Interface access for Donor x86 mainboard')).toHaveValue('if-display');
  await expect(page.getByLabel('Interface access face for Donor x86 mainboard')).toHaveValue('+x');
  await page.getByRole('button', { name: 'Build access envelope' }).click();
  await expect(accessEditor).toContainText('Compute → display · +x · 20 × 10 × 30 mm access AABB · DECLARED.');
  const accessOverlay = page.getByTestId('declared-access-overlay');
  await expect(accessOverlay).toBeVisible();
  await expect(accessOverlay).toHaveAttribute('data-aabb-blocked', 'true');
  await expect(accessOverlay).toContainText('BLOCKED');
  await expect(accessOverlay).toContainText('not service-access proof');

  // Mainboard is X=40..250, display starts X=270. A 30 mm +X access prism reaches
  // X=280 and overlaps the display by 10 mm; the smallest overlap axis is 8 mm.
  await page.getByLabel('Interface access minimum clearance mm for Donor x86 mainboard').fill('0');
  await page.getByRole('button', { name: 'Check interface access' }).click();
  await expect(accessEditor).toContainText('AABB clearance -8.000 mm is below the 0.000 mm requirement.');

  // Shrinking only the declared outward access depth to 15 mm leaves a 5 mm gap.
  await page.getByLabel('Depth interface access mm for Donor x86 mainboard').fill('15');
  await page.getByRole('button', { name: 'Build access envelope' }).click();
  await expect(accessEditor).toContainText('Compute → display · +x · 20 × 10 × 15 mm access AABB · DECLARED.');
  await expect(accessOverlay).toHaveAttribute('data-aabb-blocked', 'false');
  await expect(accessOverlay).toContainText('FREE');
  await expect(accessOverlay).toContainText('not service-access proof');
  await page.getByLabel('Interface access minimum clearance mm for Donor x86 mainboard').fill('2');
  await page.getByRole('button', { name: 'Check interface access' }).click();
  await expect(accessEditor).toContainText('AABB clearance 5.000 mm meets the 2.000 mm requirement.');
  await expect(accessEditor).toContainText('not connector mating, cable routing, service ergonomics, BREP collision truth, or fabrication authority');

  // A parent placement change invalidates its derived access envelope.
  await page.getByLabel('Placement translation X mm for Donor x86 mainboard').fill('45');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Placed in assembly: T [45, -65, 10] mm · R [0, 0, 0]° · DECLARED.');
  await expect(page.getByRole('button', { name: 'Check interface access' })).toHaveCount(0);
  await expect(accessOverlay).toHaveCount(0);

  // Replacing the upstream STEP source invalidates the placement derived from the old geometry.
  await page.getByLabel('Attach STEP geometry for Donor x86 mainboard').setInputFiles({ name: 'donor-mainboard-r2.step', mimeType: 'model/step', buffer: Buffer.from(mainboardStep) });
  await expect(page.getByTestId('step-geometry-import')).toContainText('STEP envelope attached: 210 × 130 × 18 mm · 8 points · DECLARED');
  await expect(page.getByTestId('declared-interface-access-editor')).toHaveCount(0);
  await expect(page.getByTestId('declared-clearance-checker')).toHaveCount(0);
  await expect(page.getByText('DECLARED STEP ENVELOPE', { exact: true })).toBeVisible();

  // Candidate changes still isolate all imported spatial evidence from another objective profile.
  await page.getByRole('button', { name: /Maximum reuse/ }).click();
  await page.getByRole('button', { name: 'Target', exact: true }).click();
  await expect(page.getByText('88% capability coverage', { exact: true })).toBeVisible();
  await expect(page.getByText('Missing: power', { exact: true })).toBeVisible();
  await expect(spatialProjection).toContainText('max-reuse');
  await expect(spatialProjection).toContainText('1 held');
  await expect(spatialProjection).toContainText('2 gaps');
  await expect(page.getByText('DECLARED PLACED ENVELOPE', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await expect(page.getByTestId('declared-clearance-checker')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Raw donor LCD panel.*planner selected/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Unknown old lithium pack/i })).not.toContainText('planner selected');
  await page.waitForTimeout(650);
  const constrainedCanvas = await page.locator('canvas').first().screenshot();

  // Open procurement substitutes documented compute/display geometry and closes projected resource gaps.
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

  // Proposal acceptance remains a working-design decision even under live planner/geometry state.
  await page.getByRole('button', { name: 'Accept proposal Use documented portable display to working candidate' }).click();
  await expect(page.getByText('accepted', { exact: true })).toBeVisible();
  await expect(page.getByText(/working design only/)).toBeVisible();
});