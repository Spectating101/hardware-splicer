const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const HASH_A = `sha256:${'a'.repeat(64)}`;
const HASH_B = `sha256:${'b'.repeat(64)}`;
const HASH_C = `sha256:${'c'.repeat(64)}`;
const HASH_ADAPTER = `sha256:${'d'.repeat(64)}`;
const MAINBOARD_STEP = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(100.,80.,10.));\nENDSEC;\nEND-ISO-10303-21;\n";
const DISPLAY_STEP = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(120.,90.,12.));\nENDSEC;\nEND-ISO-10303-21;\n";
const DISPLAY_REPLACEMENT_STEP = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(125.,92.,13.));\nENDSEC;\nEND-ISO-10303-21;\n";

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
        reason: 'Adapter synthesis fixture keeps both donor resources selected.',
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
  if (sourceId.includes('replacement')) {
    return { hash: HASH_C, size: [125, 92, 13], product: 'Replacement Controlled Display' };
  }
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
      anchor_point_mm: display ? [150, 40, 5] : [100, 40, 5],
      outward_normal: display ? [-1, 0, 0] : [1, 0, 0],
      snap_distance_mm: 0.02,
      max_snap_distance_mm: 5,
      face_index: display ? 4 : 5,
      face_count: 6,
      face_geom_type: 'PLANE',
      face_area_mm2: 800,
      face_center_mm: display ? [150, 40, 5] : [100, 40, 5],
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

function adapterResponse(body) {
  const vertices = [
    [100, 30, 3], [150, 30, 3], [150, 50, 3], [100, 50, 3],
    [100, 30, 7], [150, 30, 7], [150, 50, 7], [100, 50, 7],
  ];
  const triangles = [
    [0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6],
    [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2],
    [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0],
  ];
  return {
    ok: true,
    brep_adapter_candidate: {
      schema_version: 'hardware_splicer.brep_adapter_candidate.v1',
      project_id: body.project_id,
      adapter_id: body.adapter_id,
      family: 'bridge_block_v0',
      frame_id: 'assembly',
      first_anchor_id: body.first.anchor.anchor_id,
      second_anchor_id: body.second.anchor.anchor_id,
      first_object_id: body.first.anchor.object_id,
      second_object_id: body.second.anchor.object_id,
      first_placement_id: body.first.placement.placement_id,
      second_placement_id: body.second.placement.placement_id,
      first_content_hash: body.first.source.content_hash,
      second_content_hash: body.second.source.content_hash,
      status: 'ready',
      kernel_available: true,
      kernel: 'cadquery_occt',
      cadquery_version: '2.8.0',
      geometric_candidate_passed: true,
      adapter_axis: [1, 0, 0],
      adapter_midpoint_mm: [125, 40, 5],
      length_mm: 50,
      width_mm: body.parameters.width_mm,
      thickness_mm: body.parameters.thickness_mm,
      volume_mm3: 4000,
      first_parent_minimum_distance_mm: 0,
      second_parent_minimum_distance_mm: 0,
      first_parent_intersection_volume_mm3: 0,
      second_parent_intersection_volume_mm3: 0,
      first_parent_contact_passed: true,
      second_parent_contact_passed: true,
      first_parent_penetration_passed: true,
      second_parent_penetration_passed: true,
      generated_source_id: 'generated://adapter/bridge-balanced',
      generated_model_id: 'bridge-balanced',
      generated_content_hash: HASH_ADAPTER,
      generated_step_content: "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=PRODUCT('bridge-balanced','Bridge','',());\nENDSEC;\nEND-ISO-10303-21;\n",
      bbox_minimum_mm: [100, 30, 3],
      bbox_maximum_mm: [150, 50, 7],
      vertex_count: vertices.length,
      triangle_count: triangles.length,
      vertices_mm: vertices,
      triangles,
      required_evidence: [
        { field: 'material', reason: 'Material and process remain undeclared.' },
        { field: 'retention', reason: 'Mounting and retention remain unverified.' },
      ],
      metadata: {
        authority: 'declared',
        geometric_candidate_only: true,
        structural_analysis: false,
        fabrication_authorized: false,
      },
    },
    kernel_available: true,
    exact_adapter_geometry_evaluated: true,
    generated_step_available: true,
    geometric_candidate_passed: true,
    parent_raw_step_bytes_returned: false,
    geometric_candidate_only: true,
    manufacturing_authorized: false,
    fabrication_authorized: false,
    physical_measurement: false,
    automatic_execution: false,
    physical_action: false,
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

test('exact anchors synthesize a generated STEP bridge and invalidate it when a parent source changes', async ({ page }) => {
  test.setTimeout(150_000);
  await page.setViewportSize({ width: 1600, height: 1000 });
  const adapterRequests = [];

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
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(meshResponse(body)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/anchor', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(anchorResponse(body)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/adapter/synthesize', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    adapterRequests.push(body);
    expect(body.parameters.family).toBe('bridge_block_v0');
    expect(body.parameters.width_mm).toBe(20);
    expect(body.parameters.thickness_mm).toBe(4);
    expect(body.first.anchor.authority).toBe('declared');
    expect(body.second.anchor.authority).toBe('declared');
    expect(body.first.anchor.kernel_surface_snap).toBe(true);
    expect(body.second.anchor.kernel_surface_snap).toBe(true);
    expect(body.first.anchor.fabrication_authorized).toBe(false);
    expect(body.second.anchor.fabrication_authorized).toBe(false);
    expect([body.first.source.content_hash, body.second.source.content_hash].sort()).toEqual([HASH_A, HASH_B].sort());
    expect(body.first.source.content).toContain('ISO-10303-21');
    expect(body.second.source.content).toContain('ISO-10303-21');
    expect(body.first.placement.authority).toBe('declared');
    expect(body.second.placement.authority).toBe('declared');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(adapterResponse(body)) });
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
  await page.getByRole('button', { name: 'Arm surface pick' }).click();
  await clickSelectedExactMesh(page);
  await expect(page.getByTestId('exact-brep-surface-anchor')).toHaveAttribute('data-anchor-id', 'anchor-balanced-cmp-mainboard-if-display');

  const display = page.getByRole('button', { name: /Donor display \+ validated controller.*planner selected/i });
  await display.click();
  await page.getByLabel('Attach STEP geometry for Donor display + validated controller').setInputFiles({ name: 'display.step', mimeType: 'model/step', buffer: Buffer.from(DISPLAY_STEP) });
  await page.getByLabel('Placement translation X mm for Donor display + validated controller').fill('150');
  await page.getByLabel('Placement translation Y mm for Donor display + validated controller').fill('0');
  await page.getByLabel('Placement translation Z mm for Donor display + validated controller').fill('0');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await page.getByRole('button', { name: 'Generate exact mesh' }).click();
  await expect(page.getByTestId('exact-brep-render-mesh')).toBeVisible();
  await page.getByRole('button', { name: 'Arm surface pick' }).click();
  await clickSelectedExactMesh(page);
  await expect(page.getByTestId('exact-brep-surface-anchor')).toHaveAttribute('data-anchor-id', 'anchor-balanced-cmp-display-if-display');

  await page.getByRole('button', { name: 'Geometry', exact: true }).click();
  const control = page.getByTestId('brep-adapter-synthesis-control');
  await expect(control).toBeVisible();
  await expect(page.getByLabel('Adapter anchor A')).not.toHaveValue('');
  await expect(page.getByLabel('Adapter anchor B')).not.toHaveValue('');
  await page.getByRole('button', { name: 'Synthesize', exact: true }).click();

  await expect(page.getByTestId('brep-adapter-synthesis-feedback')).toHaveAttribute('data-status', 'ready');
  const result = page.getByTestId('brep-adapter-synthesis-result');
  await expect(result).toHaveAttribute('data-geometric-pass', 'true');
  await expect(result).toContainText('geometry pass');
  await expect(result).toContainText('material');
  await expect(result).toContainText('retention');
  await expect(page.getByRole('button', { name: 'Export generated STEP' })).toBeVisible();
  await expect(page.getByTestId('brep-generated-adapter-overlay')).toHaveAttribute('data-geometric-pass', 'true');
  await expect(page.getByText('fabrication blocked', { exact: true })).toBeVisible();
  expect(adapterRequests).toHaveLength(1);

  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await display.click();
  await page.getByLabel('Attach STEP geometry for Donor display + validated controller').setInputFiles({
    name: 'display-replacement.step',
    mimeType: 'model/step',
    buffer: Buffer.from(DISPLAY_REPLACEMENT_STEP),
  });
  await expect(page.getByTestId('step-geometry-import')).toContainText('Prior placement and dependent exact evidence were invalidated; re-place this source.');
  await expect(page.getByTestId('brep-generated-adapter-overlay')).toHaveCount(0);
});
