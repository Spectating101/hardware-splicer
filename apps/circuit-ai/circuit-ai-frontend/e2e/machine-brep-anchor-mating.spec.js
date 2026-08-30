const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const HASH_A = `sha256:${'a'.repeat(64)}`;
const HASH_B = `sha256:${'b'.repeat(64)}`;
const MAINBOARD_STEP = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(100.,80.,10.));\nENDSEC;\nEND-ISO-10303-21;\n";
const DISPLAY_STEP = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(120.,90.,12.));\nENDSEC;\nEND-ISO-10303-21;\n";

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
        reason: 'Anchor mating fixture keeps compute and controlled display selected.',
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

function sourceConfig(sourceId) {
  const display = sourceId.includes('display');
  return {
    hash: display ? HASH_B : HASH_A,
    size: display ? [120, 90, 12] : [100, 80, 10],
    product: display ? 'Controlled Display' : 'Donor Mainboard',
  };
}

function geometryResponse(sourceId, modelId) {
  const config = sourceConfig(sourceId);
  return {
    ok: true,
    mechanical_geometry: {
      schema_version: 'hardware_splicer.mechanical_geometry_report.v1',
      project_id: 'deck-001',
      models: [{
        schema_version: 'hardware_splicer.step_geometry.v1',
        source_id: sourceId,
        model_id: modelId,
        content_hash: config.hash,
        byte_count: 512,
        file_schema: ['AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'],
        products: [config.product],
        units: 'mm',
        entity_count: 42,
        cartesian_point_count: 8,
        bounding_box: {
          minimum: [0, 0, 0],
          maximum: config.size,
          size: config.size,
          point_count: 8,
          units: 'mm',
        },
        authority: 'declared',
        unresolved: [],
        metadata: { full_brep_validation: false, collision_analysis: false, fabrication_authorized: false },
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
  const minimum = placement.translation_mm;
  const maximum = minimum.map((value, index) => value + model.bounding_box.size[index]);
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

function meshResponse(body) {
  const config = sourceConfig(body.source.source_id);
  const [x, y, z] = body.placement.translation_mm;
  const [sx, sy, sz] = config.size;
  const vertices = [
    [x, y, z], [x + sx, y, z], [x + sx, y + sy, z], [x, y + sy, z],
    [x, y, z + sz], [x + sx, y, z + sz], [x + sx, y + sy, z + sz], [x, y + sy, z + sz],
  ];
  const triangles = [
    [0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6],
    [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2],
    [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0],
  ];
  return {
    ok: true,
    brep_mesh: {
      schema_version: 'hardware_splicer.brep_render_mesh.v1',
      project_id: body.project_id,
      source_id: body.source.source_id,
      model_id: body.source.model_id,
      content_hash: body.source.content_hash,
      frame_id: body.placement.target_frame,
      placement_id: body.placement.placement_id,
      status: 'ready',
      kernel_available: true,
      kernel: 'cadquery_occt',
      cadquery_version: '2.8.0',
      shape_valid: true,
      solid_count: 1,
      vertex_count: vertices.length,
      triangle_count: triangles.length,
      vertices_mm: vertices,
      triangles,
      tolerance_mm: body.tolerance_mm,
      angular_tolerance_rad: body.angular_tolerance_rad,
      required_evidence: [],
      metadata: {
        render_evidence_only: true,
        exact_brep_mesh_source: true,
        declared_placement_applied: true,
        physical_measurement: false,
        fabrication_authorized: false,
      },
    },
    kernel_available: true,
    exact_brep_mesh_evaluated: true,
    declared_placement_applied: true,
    vertex_count: vertices.length,
    triangle_count: triangles.length,
    raw_step_bytes_returned: false,
    render_evidence_only: true,
    full_assembly_collision: false,
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
  };
}

function anchorResponse(body) {
  const display = body.placement.object_id === 'cmp-display';
  const point = display ? [0.2, 0.1, 0] : [0, 0, 0];
  const normal = display ? [-1, 0, 0] : [1, 0, 0];
  return {
    ok: true,
    brep_surface_anchor: {
      schema_version: 'hardware_splicer.brep_surface_anchor.v1',
      project_id: body.project_id,
      anchor_id: body.anchor_id,
      interface_id: body.interface_id,
      source_id: body.source.source_id,
      model_id: body.source.model_id,
      content_hash: body.source.content_hash,
      object_id: body.placement.object_id,
      placement_id: body.placement.placement_id,
      frame_id: body.placement.target_frame,
      status: 'ready',
      kernel_available: true,
      kernel: 'cadquery_occt',
      cadquery_version: '2.8.0',
      probe_point_mm: body.probe_point_mm,
      anchor_point_mm: point,
      outward_normal: normal,
      snap_distance_mm: 0.05,
      max_snap_distance_mm: 5,
      face_index: display ? 4 : 5,
      face_count: 6,
      face_geom_type: 'PLANE',
      face_area_mm2: 1000,
      face_center_mm: point,
      solid_count: 1,
      required_evidence: [],
      metadata: {
        authority: 'declared',
        kernel_surface_snap: true,
        interface_binding_declared: true,
        connector_mating_verified: false,
        physical_measurement: false,
        fabrication_authorized: false,
      },
    },
    kernel_available: true,
    exact_brep_surface_anchor_evaluated: true,
    interface_binding_declared: true,
    raw_step_bytes_returned: false,
    authority: 'declared',
    connector_mating_verified: false,
    fit_verified: false,
    full_assembly_collision: false,
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
  };
}

function matingResponse(body) {
  const req = body.requirements;
  const lateral = 0.1;
  const axial = 0.2;
  const normalError = 0;
  const normalPassed = normalError <= Number(req.max_normal_opposition_error_deg);
  const lateralPassed = lateral <= Number(req.max_lateral_offset_mm);
  const axialError = Math.abs(axial - Number(req.target_axial_offset_mm));
  const axialPassed = axialError <= Number(req.axial_offset_tolerance_mm);
  const axisEvaluated = Array.isArray(req.declared_mating_axis);
  const engagementRequired = req.required_engagement_depth_mm !== null && req.required_engagement_depth_mm !== undefined;
  const engagementEvaluated = engagementRequired && req.declared_engagement_depth_mm !== null && req.declared_engagement_depth_mm !== undefined;
  const engagementPassed = engagementEvaluated
    ? Number(req.declared_engagement_depth_mm) >= Number(req.required_engagement_depth_mm)
    : null;
  const unknown = engagementRequired && !engagementEvaluated;
  const passed = unknown ? null : normalPassed && lateralPassed && axialPassed && (engagementPassed ?? true);
  return {
    ok: true,
    brep_anchor_mating: {
      schema_version: 'hardware_splicer.brep_anchor_mating.v1',
      project_id: body.project_id,
      mating_id: body.mating_id,
      interface_id: body.first_anchor.interface_id,
      frame_id: body.first_anchor.frame_id,
      first_anchor_id: body.first_anchor.anchor_id,
      second_anchor_id: body.second_anchor.anchor_id,
      first_object_id: body.first_anchor.object_id,
      second_object_id: body.second_anchor.object_id,
      status: unknown ? 'unknown' : 'ready',
      geometric_mating_passed: passed,
      anchor_separation_mm: Math.hypot(axial, lateral),
      normal_opposition_error_deg: normalError,
      mating_axis: [-1, 0, 0],
      mating_axis_source: axisEvaluated ? 'declared' : 'first_anchor_normal',
      signed_axial_offset_mm: axial,
      target_axial_offset_mm: Number(req.target_axial_offset_mm),
      axial_offset_error_mm: axialError,
      axial_offset_passed: axialPassed,
      lateral_offset_mm: lateral,
      lateral_offset_passed: lateralPassed,
      normal_opposition_passed: normalPassed,
      declared_axis_alignment_evaluated: axisEvaluated,
      first_axis_alignment_error_deg: axisEvaluated ? 0 : null,
      second_axis_alignment_error_deg: axisEvaluated ? 0 : null,
      axis_alignment_passed: axisEvaluated ? true : null,
      coaxiality_evaluated: axisEvaluated,
      coaxial_offset_mm: axisEvaluated ? lateral : null,
      engagement_evaluated: engagementEvaluated,
      required_engagement_depth_mm: engagementRequired ? Number(req.required_engagement_depth_mm) : null,
      declared_engagement_depth_mm: engagementEvaluated ? Number(req.declared_engagement_depth_mm) : null,
      engagement_passed: engagementPassed,
      required_evidence: unknown ? [{ field: 'declared_engagement_depth_mm', reason: 'required engagement depth needs a declared actual depth' }] : [],
      metadata: {
        common_frame: true,
        connector_mating_verified: false,
        swept_engagement_collision: false,
        physical_measurement: false,
        fabrication_authorized: false,
      },
    },
    mating_geometry_evaluated: !unknown,
    geometric_mating_passed: passed,
    common_frame: true,
    authority: 'declared',
    geometric_mating_only: true,
    connector_mating_verified: false,
    protocol_compatibility_verified: false,
    pin_compatibility_verified: false,
    retention_verified: false,
    swept_engagement_collision: false,
    whole_assembly_collision: false,
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

async function clickSelectedExactMesh(page) {
  const exactMesh = page.getByTestId('exact-brep-render-mesh');
  await expect(exactMesh).toHaveAttribute('data-surface-pick-armed', 'true');
  const canvas = page.locator('canvas').first();
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } });
  await expect(page.getByTestId('brep-surface-anchor-feedback')).toHaveAttribute('data-pick-status', 'success');
}

test('two exact BREP anchors evaluate pair geometry without promoting connector mating authority', async ({ page }) => {
  test.setTimeout(150_000);
  await page.setViewportSize({ width: 1600, height: 1000 });
  const anchorRequests = [];
  const matingRequests = [];

  await page.route('**/api/proxy/resource/strategy', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(strategyResponse(body.strategy_mode || 'hybrid')) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/parse', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    const source = body.sources[0];
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(geometryResponse(source.source_id, source.model_id)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/place', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(placementResponse(body)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/mesh', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    const expectedHash = body.source.source_id.includes('display') ? HASH_B : HASH_A;
    expect(body.source.content_hash).toBe(expectedHash);
    expect(body.source.content).toContain('ISO-10303-21');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(meshResponse(body)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/anchor', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    anchorRequests.push(body);
    expect(body.interface_id).toBe('if-display');
    expect(body.placement.authority).toBe('declared');
    expect(body.source.content_hash).toBe(body.placement.object_id === 'cmp-display' ? HASH_B : HASH_A);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(anchorResponse(body)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/mating', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    matingRequests.push(body);
    expect(body.first_anchor.anchor_id).toBe('anchor-balanced-cmp-display-if-display');
    expect(body.second_anchor.anchor_id).toBe('anchor-balanced-cmp-mainboard-if-display');
    expect(body.first_anchor.interface_id).toBe('if-display');
    expect(body.second_anchor.interface_id).toBe('if-display');
    expect(body.first_anchor.frame_id).toBe('assembly');
    expect(body.second_anchor.frame_id).toBe('assembly');
    expect(body.first_anchor.kernel_surface_snap).toBe(true);
    expect(body.second_anchor.kernel_surface_snap).toBe(true);
    expect(body.first_anchor.connector_mating_verified).toBe(false);
    expect(body.second_anchor.connector_mating_verified).toBe(false);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(matingResponse(body)) });
  });

  await page.goto(`${APP_URL}/workbench`);
  await expect(page.getByText('live planner', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Resources', exact: true }).click();

  const mainboard = page.getByRole('button', { name: /Donor x86 mainboard.*planner selected/i });
  await mainboard.click();
  await page.getByLabel('Attach STEP geometry for Donor x86 mainboard').setInputFiles({ name: 'mainboard.step', mimeType: 'model/step', buffer: Buffer.from(MAINBOARD_STEP) });
  await page.getByLabel('Placement translation X mm for Donor x86 mainboard').fill('0');
  await page.getByLabel('Placement translation Y mm for Donor x86 mainboard').fill('0');
  await page.getByLabel('Placement translation Z mm for Donor x86 mainboard').fill('0');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await page.getByRole('button', { name: 'Generate exact mesh' }).click();
  await expect(page.getByTestId('exact-brep-render-mesh')).toBeVisible();
  await expect(page.getByLabel('BREP anchor interface for Donor x86 mainboard')).toHaveValue('if-display');
  await page.getByRole('button', { name: 'Arm surface pick' }).click();
  await clickSelectedExactMesh(page);
  await expect(page.getByTestId('exact-brep-surface-anchor')).toHaveAttribute('data-anchor-id', 'anchor-balanced-cmp-mainboard-if-display');
  await expect(page.getByTestId('brep-anchor-mating-control')).toHaveCount(0);

  const display = page.getByRole('button', { name: /Donor display \+ validated controller.*planner selected/i });
  await display.click();
  await page.getByLabel('Attach STEP geometry for Donor display + validated controller').setInputFiles({ name: 'display.step', mimeType: 'model/step', buffer: Buffer.from(DISPLAY_STEP) });
  await page.getByLabel('Placement translation X mm for Donor display + validated controller').fill('150');
  await page.getByLabel('Placement translation Y mm for Donor display + validated controller').fill('0');
  await page.getByLabel('Placement translation Z mm for Donor display + validated controller').fill('0');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await page.getByRole('button', { name: 'Generate exact mesh' }).click();
  await expect(page.getByTestId('exact-brep-render-mesh')).toBeVisible();
  await expect(page.getByLabel('BREP anchor interface for Donor display + validated controller')).toHaveValue('if-display');
  await page.getByRole('button', { name: 'Arm surface pick' }).click();
  await clickSelectedExactMesh(page);
  await expect(page.getByTestId('exact-brep-surface-anchor')).toHaveAttribute('data-anchor-id', 'anchor-balanced-cmp-display-if-display');
  expect(anchorRequests).toHaveLength(2);

  const mating = page.getByTestId('brep-anchor-mating-control');
  await expect(mating).toContainText('if-display · cmp-display ↔ cmp-mainboard');
  await expect(mating).toContainText('optional for coaxiality');
  await page.getByRole('button', { name: 'Evaluate anchor mating' }).click();
  const result = page.getByTestId('brep-anchor-mating-result');
  await expect(page.getByTestId('brep-anchor-mating-feedback')).toContainText('WITHIN the declared geometric mating tolerances');
  await expect(result).toHaveAttribute('data-geometric-pass', 'true');
  await expect(result).toContainText('0.100 mm');
  await expect(result).toContainText('not evaluated · declare axis');

  await page.getByLabel('Declared mating axis X').fill('1');
  await page.getByLabel('Declared mating axis Y').fill('0');
  await page.getByLabel('Declared mating axis Z').fill('0');
  await page.getByRole('button', { name: 'Evaluate anchor mating' }).click();
  await expect(result).toContainText('0.100 mm');
  expect(matingRequests.at(-1).requirements.declared_mating_axis).toEqual([1, 0, 0]);

  await page.getByLabel('Maximum mating lateral offset mm').fill('0.05');
  await page.getByRole('button', { name: 'Evaluate anchor mating' }).click();
  await expect(page.getByTestId('brep-anchor-mating-feedback')).toContainText('OUTSIDE the declared geometric mating tolerances');
  await expect(result).toHaveAttribute('data-geometric-pass', 'false');

  // A required engagement depth with no declared actual depth must stay UNKNOWN;
  // two exact surface points cannot manufacture engagement semantics.
  await page.getByLabel('Maximum mating lateral offset mm').fill('0.5');
  await page.getByLabel('Required mating engagement depth mm').fill('4');
  await page.getByRole('button', { name: 'Evaluate anchor mating' }).click();
  await expect(page.getByTestId('brep-anchor-mating-feedback')).toHaveAttribute('data-mating-status', 'unknown');
  await expect(page.getByTestId('brep-anchor-mating-feedback')).toContainText('Mating geometry UNKNOWN');
  expect(matingRequests.at(-1).requirements.declared_engagement_depth_mm).toBeNull();
  expect(matingRequests).toHaveLength(4);
});
