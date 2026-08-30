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
      coverage: { covered_capabilities: ['x86_compute', 'display_or_ui'], missing_capabilities: [], coverage_score: 1 },
      build_readiness: {
        status: 'prototype_after_evidence',
        reason: 'Adaptive BREP refinement fixture keeps compute and controlled display selected.',
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
        bounding_box: { minimum: [0, 0, 0], maximum: config.size, size: config.size, point_count: 8, units: 'mm' },
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

function refinementResponse(body) {
  const startX = Number(body.moving_start_placement.translation_mm[0]);
  const endX = Number(body.moving_end_placement.translation_mm[0]);
  const pathLength = Math.abs(endX - startX);
  const clearanceLow = 0.7992;
  const clearanceHigh = 0.8;
  const interferenceLow = 0.8;
  const interferenceHigh = 0.8008;
  return {
    ok: true,
    brep_mating_path_refinement: {
      schema_version: 'hardware_splicer.brep_mating_path_refinement.v1',
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
      path_length_mm: pathLength,
      coarse_sample_count: body.sample_count,
      coarse_evaluated_sample_count: body.sample_count,
      refinement_candidate_count: 2,
      refined_boundary_count: 2,
      refinement_evaluated_pose_count: 20,
      total_exact_pose_evaluations: body.sample_count + 20,
      refinement_max_depth: body.refinement_max_depth,
      refinement_fraction_tolerance: body.refinement_fraction_tolerance,
      candidates: [],
      brackets: [
        {
          boundary_index: 0,
          kind: 'clearance_boundary',
          lower_fraction: clearanceLow,
          upper_fraction: clearanceHigh,
          lower_path_distance_mm: pathLength * clearanceLow,
          upper_path_distance_mm: pathLength * clearanceHigh,
          bracket_width_fraction: clearanceHigh - clearanceLow,
          bracket_width_mm: pathLength * (clearanceHigh - clearanceLow),
          lower_state: 'clear',
          upper_state: 'contact',
          lower_minimum_distance_mm: 0.02,
          upper_minimum_distance_mm: 0,
          lower_intersection_volume_mm3: 0,
          upper_intersection_volume_mm3: 0,
          refinement_depth: 8,
          evaluation_count: 10,
          converged: true,
          max_depth_reached: false,
        },
        {
          boundary_index: 1,
          kind: 'interference_boundary',
          lower_fraction: interferenceLow,
          upper_fraction: interferenceHigh,
          lower_path_distance_mm: pathLength * interferenceLow,
          upper_path_distance_mm: pathLength * interferenceHigh,
          bracket_width_fraction: interferenceHigh - interferenceLow,
          bracket_width_mm: pathLength * (interferenceHigh - interferenceLow),
          lower_state: 'contact',
          upper_state: 'interference',
          lower_minimum_distance_mm: 0,
          upper_minimum_distance_mm: 0,
          lower_intersection_volume_mm3: 0,
          upper_intersection_volume_mm3: 2,
          refinement_depth: 8,
          evaluation_count: 10,
          converged: true,
          max_depth_reached: false,
        },
      ],
      required_evidence: [],
      metadata: {
        adaptive_refinement: true,
        transition_brackets_only: true,
        unique_transition_pose_verified: false,
        monotonicity_inside_bracket_verified: false,
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
    adaptive_transition_refinement: true,
    transition_brackets_only: true,
    unique_transition_pose_verified: false,
    monotonicity_inside_bracket_verified: false,
    refinement_evaluated: true,
    refinement_required: true,
    refined_boundary_count: 2,
    refinement_evaluated_pose_count: 20,
    total_exact_pose_evaluations: body.sample_count + 20,
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

test('adaptive exact BREP refinement renders bounded predicate brackets without collapsing them to point events', async ({ page }) => {
  test.setTimeout(150_000);
  await page.setViewportSize({ width: 1600, height: 1000 });
  const refinementRequests = [];

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
  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/mating-path/refine', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    refinementRequests.push(body);
    expect(body.moving_source.source_id).toBe('display.step');
    expect(body.moving_source.content_hash).toBe(HASH_B);
    expect(body.fixed_source.source_id).toBe('mainboard.step');
    expect(body.fixed_source.content_hash).toBe(HASH_A);
    expect(body.moving_source.content).toBe(DISPLAY_STEP);
    expect(body.fixed_source.content).toBe(MAINBOARD_STEP);
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
    expect(body.contact_distance_tolerance_mm).toBe(0.001);
    expect(body.refinement_max_depth).toBe(8);
    expect(body.refinement_fraction_tolerance).toBe(0.001);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(refinementResponse(body)) });
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
  await expect(page.getByTestId('brep-mating-path-refinement-control')).toHaveCount(0);

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

  const refinement = page.getByTestId('brep-mating-path-refinement-control');
  await expect(refinement).toContainText('exact OCCT · range only');
  await expect(refinement).toContainText('No unique contact pose or continuous clearance is inferred');
  await expect(page.getByLabel('Adaptive refinement end translation X')).toHaveValue('150');
  await page.getByLabel('Adaptive refinement end translation X').fill('5');
  await page.getByLabel('Refined mating path coarse sample count').fill('6');
  await page.getByRole('button', { name: 'Refine sampled transitions' }).click();

  await expect(page.getByTestId('brep-mating-path-refinement-feedback')).toContainText('Refined 2 predicate-change brackets with 20 additional exact BREP pose evaluations');
  const result = page.getByTestId('brep-mating-path-refinement-result');
  await expect(result).toContainText('2 predicate brackets');
  await expect(result).toContainText('26 total exact poses');
  const brackets = page.getByTestId('brep-transition-bracket');
  await expect(brackets).toHaveCount(2);
  await expect(brackets.nth(0)).toContainText('clearance_boundary');
  await expect(brackets.nth(0)).toContainText('clear → contact');
  await expect(brackets.nth(0)).toContainText('fraction 0.799200–0.800000');
  await expect(brackets.nth(1)).toContainText('interference_boundary');
  await expect(brackets.nth(1)).toContainText('contact → interference');
  await expect(refinement).toContainText('They do not prove a unique transition pose');
  expect(refinementRequests).toHaveLength(1);

  // Any refinement-parameter edit invalidates the old bracket evidence immediately.
  await page.getByLabel('Mating path refinement fraction tolerance').fill('0.002');
  await expect(page.getByTestId('brep-mating-path-refinement-result')).toHaveCount(0);
  expect(refinementRequests).toHaveLength(1);

  // Client-side depth bounds fail closed and do not issue a backend request.
  await page.getByLabel('Mating path refinement max depth').fill('13');
  await page.getByRole('button', { name: 'Refine sampled transitions' }).click();
  await expect(page.getByTestId('brep-mating-path-refinement-feedback')).toContainText('Refinement depth must be an integer from 1 through 12');
  expect(refinementRequests).toHaveLength(1);
});
