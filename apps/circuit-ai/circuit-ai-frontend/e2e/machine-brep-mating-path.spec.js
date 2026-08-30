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
        reason: 'Sampled mating-path fixture keeps compute and controlled display selected.',
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
      metadata: { render_evidence_only: true, exact_brep_mesh_source: true, declared_placement_applied: true, physical_measurement: false, fabrication_authorized: false },
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
      metadata: { authority: 'declared', kernel_surface_snap: true, interface_binding_declared: true, connector_mating_verified: false, physical_measurement: false, fabrication_authorized: false },
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

function matingPathResponse(body) {
  const startX = Number(body.moving_start_placement.translation_mm[0]);
  const endX = Number(body.moving_end_placement.translation_mm[0]);
  const pathLength = Math.abs(endX - startX);
  return {
    ok: true,
    brep_mating_path: {
      schema_version: 'hardware_splicer.brep_mating_path_sweep.v1',
      project_id: body.project_id,
      sweep_id: body.sweep_id,
      moving_source_id: body.moving_source.source_id,
      fixed_source_id: body.fixed_source.source_id,
      moving_model_id: body.moving_source.model_id,
      fixed_model_id: body.fixed_source.model_id,
      moving_content_hash: body.moving_source.content_hash,
      fixed_content_hash: body.fixed_source.content_hash,
      moving_object_id: body.moving_start_placement.object_id,
      fixed_object_id: body.fixed_placement.object_id,
      frame_id: body.moving_start_placement.target_frame,
      status: 'ready',
      kernel_available: true,
      kernel: 'cadquery_occt',
      cadquery_version: '2.8.0',
      sample_count: body.sample_count,
      evaluated_sample_count: body.sample_count,
      path_length_mm: pathLength,
      engagement_start_fraction: body.engagement_start_fraction,
      contact_distance_tolerance_mm: body.contact_distance_tolerance_mm,
      sampled_path_interference_free: false,
      approach_interference_free: true,
      engagement_region_evaluated: true,
      engagement_region_interference_free: false,
      first_contact_sample_index: 4,
      first_contact_fraction: 0.8,
      first_contact_path_distance_mm: pathLength * 0.8,
      first_interference_sample_index: 5,
      first_interference_fraction: 1,
      first_interference_path_distance_mm: pathLength,
      samples: [],
      required_evidence: [],
      metadata: {
        sampled_path_only: true,
        continuous_path_verified: false,
        continuous_collision_free_verified: false,
        aabb_fallback_used: false,
        connector_mating_verified: false,
        whole_assembly_collision: false,
        physical_measurement: false,
        fabrication_authorized: false,
      },
    },
    kernel_available: true,
    sampled_path_evaluated: true,
    sampled_path_interference_free: false,
    approach_interference_free: true,
    engagement_region_evaluated: true,
    engagement_region_interference_free: false,
    first_contact_sample_index: 4,
    first_interference_sample_index: 5,
    aabb_fallback_used: false,
    authority: 'declared',
    sampled_path_only: true,
    continuous_path_verified: false,
    continuous_collision_free_verified: false,
    connector_mating_verified: false,
    protocol_compatibility_verified: false,
    pin_compatibility_verified: false,
    retention_verified: false,
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

test('exact BREP anchor pair evaluates bounded mating-path samples without claiming continuous clearance', async ({ page }) => {
  test.setTimeout(150_000);
  await page.setViewportSize({ width: 1600, height: 1000 });
  const pathRequests = [];

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
    expect(body.source.content_hash).toBe(sourceConfig(body.source.source_id).hash);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(meshResponse(body)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/anchor', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    expect(body.interface_id).toBe('if-display');
    expect(body.source.content_hash).toBe(body.placement.object_id === 'cmp-display' ? HASH_B : HASH_A);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(anchorResponse(body)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/mating-path', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    pathRequests.push(body);
    expect(body.moving_source.source_id).toBe('display.step');
    expect(body.moving_source.content_hash).toBe(HASH_B);
    expect(body.fixed_source.source_id).toBe('mainboard.step');
    expect(body.fixed_source.content_hash).toBe(HASH_A);
    expect(body.moving_start_placement.object_id).toBe('cmp-display');
    expect(body.fixed_placement.object_id).toBe('cmp-mainboard');
    expect(body.moving_start_placement.target_frame).toBe('assembly');
    expect(body.moving_end_placement.target_frame).toBe('assembly');
    expect(body.fixed_placement.target_frame).toBe('assembly');
    expect(body.moving_start_placement.authority).toBe('declared');
    expect(body.moving_end_placement.authority).toBe('declared');
    expect(body.fixed_placement.authority).toBe('declared');
    expect(body.moving_start_placement.rotation_deg_xyz).toEqual(body.moving_end_placement.rotation_deg_xyz);
    expect(body.sample_count).toBe(6);
    expect(body.engagement_start_fraction).toBe(0.8);
    expect(body.contact_distance_tolerance_mm).toBe(0.001);
    expect(body.moving_source.content).toBe(DISPLAY_STEP);
    expect(body.fixed_source.content).toBe(MAINBOARD_STEP);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(matingPathResponse(body)) });
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
  await expect(page.getByTestId('brep-mating-path-control')).toHaveCount(0);

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

  const path = page.getByTestId('brep-mating-path-control');
  await expect(path).toContainText('exact BREP · not continuous');
  await expect(path).toContainText('Moving cmp-display');
  await expect(page.getByLabel('Mating path end translation X')).toHaveValue('150');
  await page.getByLabel('Mating path end translation X').fill('5');
  await page.getByLabel('Mating path sample count').fill('6');
  await page.getByLabel('Mating path engagement start fraction').fill('0.8');
  await page.getByRole('button', { name: 'Evaluate sampled path' }).click();

  await expect(page.getByTestId('brep-mating-path-feedback')).toContainText('At least one evaluated BREP sample has volumetric interference');
  const result = page.getByTestId('brep-mating-path-result');
  await expect(result).toContainText('6 exact samples · path 145.000 mm');
  await expect(result).toContainText('first sampled contact: #4 at 116.000 mm');
  await expect(result).toContainText('first sampled interference: #5 at 145.000 mm');
  await expect(result).toContainText('engagement region: sampled interference');
  await expect(path).toContainText('Unsampled motion remains unverified');
  expect(pathRequests).toHaveLength(1);

  // Requirement edits invalidate the old result before any new request is accepted.
  await page.getByLabel('Mating path end translation X').fill('10');
  await expect(page.getByTestId('brep-mating-path-result')).toHaveCount(0);
  expect(pathRequests).toHaveLength(1);

  // Client-side sample bounds fail closed and do not issue a backend request.
  await page.getByLabel('Mating path sample count').fill('1');
  await page.getByRole('button', { name: 'Evaluate sampled path' }).click();
  await expect(page.getByTestId('brep-mating-path-feedback')).toContainText('Sample count must be an integer from 2 through 33');
  expect(pathRequests).toHaveLength(1);
});
