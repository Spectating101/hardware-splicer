const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const PROJECT_ID = 'durable-workbench';
const HASH_A = `sha256:${'a'.repeat(64)}`;
const HASH_B = `sha256:${'b'.repeat(64)}`;
const MAINBOARD_SOURCE = 'registered-mainboard-step';
const DISPLAY_SOURCE = 'registered-display-step';
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
        reason: 'Durable BREP fixture keeps compute and controlled display selected.',
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
  const display = sourceId === DISPLAY_SOURCE;
  return {
    hash: display ? HASH_B : HASH_A,
    size: display ? [120, 90, 12] : [100, 80, 10],
    product: display ? 'Controlled Display' : 'Donor Mainboard',
  };
}

function geometryReport(sourceId) {
  const config = sourceConfig(sourceId);
  return {
    schema_version: 'hardware_splicer.mechanical_geometry_report.v1',
    project_id: PROJECT_ID,
    models: [{
      schema_version: 'hardware_splicer.step_geometry.v1',
      source_id: sourceId,
      model_id: sourceId,
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
      metadata: {
        registered_source_hash_reverified: true,
        authority_bounded_by_parent_upload: true,
        physical_authority_unchanged: true,
      },
    }],
    mounts: [],
    checks: [],
    status: 'candidate',
    required_evidence: [],
    metadata: {},
  };
}

function parserResponse(sourceId, revision) {
  const config = sourceConfig(sourceId);
  return {
    ok: true,
    registered: true,
    project_id: PROJECT_ID,
    revision,
    parser_run: {
      schema_version: 'hardware_splicer.stored_source_parser.v1',
      parser_identity: 'hardware_splicer.stored_source_parser.python.v1',
      project_id: PROJECT_ID,
      source_id: sourceId,
      content_hash: config.hash,
      parser_route: 'step_geometry',
      status: 'parsed',
      authority_ceiling: 'declared',
      parsed_output: {
        step_model: geometryReport(sourceId).models[0],
        mechanical_geometry: geometryReport(sourceId),
        summary: { model_id: sourceId, units: 'mm', has_bounding_box: true },
      },
      derived_sources: [],
      limitations: ['Bounded STEP identity and point envelope only.'],
      raw_bytes_returned: false,
      automatic_authorization: false,
      metadata: { parser_reverified_hash: true, physical_authority_unchanged: true },
    },
    authority_unchanged: true,
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
        source_materialization: 'registered_blob_hash_reverified_server_side',
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
    registered_source_materialized: true,
    registered_source_hash_reverified: true,
    raw_registered_source_bytes_returned: false,
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
        source_materialization: 'registered_blob_hash_reverified_server_side',
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
    registered_source_materialized: true,
    registered_source_hash_reverified: true,
    raw_registered_source_bytes_returned: false,
  };
}

function refinementResponse(body) {
  const pathLength = Math.abs(Number(body.moving_end_placement.translation_mm[0]) - Number(body.moving_start_placement.translation_mm[0]));
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
        source_materialization: 'registered_blob_hash_reverified_server_side',
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
    max_total_pose_budget: 256,
    aabb_fallback_used: false,
    raw_step_bytes_returned: false,
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
    registered_sources_materialized: true,
    registered_source_hashes_reverified: true,
    moving_registered_source_hash_reverified: true,
    fixed_registered_source_hash_reverified: true,
    raw_registered_source_bytes_returned: false,
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

test('project-bound workbench keeps exact BREP evidence on registered hash-reverified sources without browser STEP replay', async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1600, height: 1000 });

  let ingestCount = 0;
  let bindingCount = 0;
  const placementPersistenceRequests = [];
  const storedMeshRequests = [];
  const storedAnchorRequests = [];
  const storedRefinementRequests = [];
  const inlineCalls = [];

  await page.route('**/api/proxy/resource/strategy', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(strategyResponse(body.strategy_mode || 'hybrid')) });
  });

  await page.route(new RegExp(`/api/proxy/engineering/projects/${PROJECT_ID}$`), async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        project: {
          revision: 1,
          snapshot: {
            projectId: PROJECT_ID,
            projectName: 'Durable workbench fixture',
            engineeringSources: [],
            machineWorkbenchStepBindings: [],
          },
        },
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/sources/ingest-file`, async (route) => {
    ingestCount += 1;
    const multipart = (route.request().postDataBuffer() || Buffer.alloc(0)).toString('utf8');
    const mainboard = multipart.includes('mainboard.step');
    const sourceId = mainboard ? MAINBOARD_SOURCE : DISPLAY_SOURCE;
    const hash = mainboard ? HASH_A : HASH_B;
    const expectedRevision = mainboard ? 1 : 5;
    expect(multipart).toContain('name="expected_revision"');
    expect(multipart).toContain(`\r\n\r\n${expectedRevision}\r\n`);
    expect(multipart).toContain('name="metadata_json"');
    expect(multipart).toContain(mainboard ? 'res-mainboard-donor' : 'res-display-controlled');
    expect(multipart).toContain(mainboard ? 'cmp-mainboard' : 'cmp-display');
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        project_id: PROJECT_ID,
        revision: mainboard ? 2 : 6,
        ingestion: {
          source_id: sourceId,
          content_hash: hash,
          source_descriptor: {
            source_id: sourceId,
            content_hash: hash,
            authority_ceiling: 'declared',
            metadata: {
              parser_route: 'step_geometry',
              parser_disposition: 'structured',
              original_filename: mainboard ? 'mainboard.step' : 'display.step',
            },
          },
          metadata: { raw_bytes_in_response: false },
        },
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/sources/*/parse`, async (route) => {
    const url = new URL(route.request().url());
    const sourceId = decodeURIComponent(url.pathname.split('/sources/')[1].split('/parse')[0]);
    const body = JSON.parse(route.request().postData() || '{}');
    const mainboard = sourceId === MAINBOARD_SOURCE;
    expect(body.expected_revision).toBe(mainboard ? 2 : 6);
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify(parserResponse(sourceId, mainboard ? 3 : 7)),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/workbench/step-bindings`, async (route) => {
    bindingCount += 1;
    const body = JSON.parse(route.request().postData() || '{}');
    const mainboard = body.resource_id === 'res-mainboard-donor';
    expect(body.expected_revision).toBe(mainboard ? 3 : 7);
    expect(body.candidate_id).toBe('balanced');
    expect(body.entity_id).toBe(mainboard ? 'cmp-mainboard' : 'cmp-display');
    expect(body.source_id).toBe(mainboard ? MAINBOARD_SOURCE : DISPLAY_SOURCE);
    expect(body.model_id).toBe(body.source_id);
    expect(body.content_hash).toBe(mainboard ? HASH_A : HASH_B);
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        registered: true,
        project_id: PROJECT_ID,
        revision: mainboard ? 4 : 8,
        workbench_step_binding: {
          schema_version: 'hardware_splicer.workbench_step_binding.v1',
          candidate_id: body.candidate_id,
          resource_id: body.resource_id,
          entity_id: body.entity_id,
          source_id: body.source_id,
          model_id: body.model_id,
          content_hash: body.content_hash,
          source_binding_only: true,
          physical_authority_unchanged: true,
          automatic_authorization: false,
        },
        registered_source_hash_reverified: true,
        raw_registered_source_bytes_returned: false,
        authority_unchanged: true,
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/workbench/placements`, async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    placementPersistenceRequests.push(body);
    const mainboard = body.resource_id === 'res-mainboard-donor';
    expect(body.expected_revision).toBe(Mainboard ? 4 : 8);
    expect(body.candidate_id).toBe('balanced');
    expect(body.entity_id).toBe(mainboard ? 'cmp-mainboard' : 'cmp-display');
    expect(body.source_id).toBe(mainboard ? MAINBOARD_SOURCE : DISPLAY_SOURCE);
    expect(body.model_id).toBe(body.source_id);
    expect(body.content_hash).toBe(mainboard ? HASH_A : HASH_B);
    expect(body.placement_id).toBe(mainboard ? 'placement-balanced-res-mainboard-donor' : 'placement-balanced-res-display-controlled');
    expect(body.target_frame).toBe('assembly');
    expect(body.translation_mm).toEqual(mainboard ? [0, 0, 0] : [150, 0, 0]);
    expect(body.rotation_deg_xyz).toEqual([0, 0, 0]);
    expect(body.authority).toBe('declared');
    await route.fulfill {
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        registered: true,
        project_id: PROJECT_ID,
        revision: mainboard ? 5 : 9,
        workbench_placement: {
          schema_version: 'hardware_splicer.workbench_declared_placement.v1',
          candidate_id: body.candidate_id,
          resource_id: body.resource_id,
          entity_id: body.entity_id,
          source_id: body.source_id,
          model_id: body.model_id,
          content_hash: body.content_hash,
          placement_id: body.placement_id,
          target_frame: body.target_frame,
          translation_mm: body.translation_mm,
          rotation_deg_xyz: body.rotation_deg_xyz,
          authority: 'declared',
          source_binding_required: true,
          registered_source_hash_reverified: true,
          derived_geometry_persisted: false,
          physical_authority_unchanged: true,
          automatic_authorization: false,
          fabrication_authorized: false,
          power_on_authorized: false,
          motion_authorized: false,
          release_authorized: false,
        },
        registered_source_hash_reverified: true,
        derived_geometry_persisted: false,
        physical_authority_unchanged: true,
      }),
    });
  });

  await page.route('**/api/proxy/engineering/mechanical/geometry/place', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(placementResponse(body)) });
  });

  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/mesh/stored', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    storedMeshRequests.push(body);
    expect(body.project_id).toBe(PROJECT_ID);
    expect(body.source.content).toBeUndefined();
    expect(body.source.model_id).toBe(body.source.source_id);
    expect([MAINBOARD_SOURCE, DISPLAY_SOURCE]).toContain(body.source.source_id);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(meshResponse(body)) });
  });

  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/anchor/stored', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    storedAnchorRequests.push(body);
    expect(body.project_id).toBe(PROJECT_ID);
    expect(body.interface_id).toBe('if-display');
    expect(body.source.content).toBeUndefined();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(anchorResponse(body)) });
  });

  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/mating-path/refine/stored', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    storedRefinementRequests.push(body);
    expect(body.project_id).toBe(PROJECT_ID);
    expect(body.moving_source.source_id).toBe(DISPLAY_SOURCE);
    expect(body.fixed_source.source_id).toBe(MAINBOARD_SOURCE);
    expect(body.moving_source.content).toBeUndefined();
    expect(body.fixed_source.content).toBeUndefined();
    expect(body.moving_source.content_hash).toBe(HASH_B);
    expect(body.fixed_source.content_hash).toBe(HASH_A);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(refinementResponse(body)) });
  });

  for (const path of [
    'geometry/parse',
    'geometry/brep/mesh',
    'geometry/brep/anchor',
    'geometry/brep/mating-path/refine',
  ]) {
    await page.route(`**/api/proxy/engineering/mechanical/${path}`, async (route) => {
      inlineCalls.push(route.request().url());
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ ok: false, error: 'inline route forbidden in durable test' }) });
    });
  }

  await page.goto(`${APP_URL}/workbench?project=${PROJECT_ID}`);
  await expect(page.getByText('live planner', { exact: true })).toBeVisible();
  await expect(page.getByTestId('workbench-project-provenance')).toContainText(`Project ${PROJECT_ID} · revision 1`);
  await page.getByRole('button', { name: 'Resources', exact: true }).click();

  const mainboard = page.getByRole('button', { name: /Donor x86 mainboard.*planner selected/i });
  await mainboard.click();
  await page.getByLabel('Attach STEP geometry for Donor x86 mainboard').setInputFiles({ name: 'mainboard.step', mimeType: 'model/step', buffer: Buffer.from(MAINBOARD_STEP) });
  await expect(page.getByTestId('workbench-project-provenance')).toContainText('revision 4');
  await page.getByLabel('Placement translation X mm for Donor x86 mainboard').fill('0');
  await page.getByLabel('Placement translation Y mm for Donor x86 mainboard').fill('0');
  await page.getByLabel('Placement translation Z mm for Donor x86 mainboard').fill('0');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await expect(page.getByTestId('brep-render-mesh-control')).toContainText('registered server-side STEP blob');
  await page.getByRole('button', { name: 'Generate exact mesh' }).click();
  await expect(page.getByTestId('brep-render-mesh-control')).toContainText('registered blob hash reverified');
  await page.getByRole('button', { name: 'Arm surface pick' }).click();
  await clickSelectedExactMesh(page);
  await expect(page.getByTestId('exact-brep-surface-anchor')).toHaveAttribute('data-anchor-id', 'anchor-balanced-cmp-mainboard-if-display');

  const display = page.getByRole('button', { name: /Donor display \+ validated controller.*planner selected/i });
  await display.click();
  await page.getByLabel('Attach STEP geometry for Donor display + validated controller').setInputFiles({ name: 'display.step', mimeType: 'model/step', buffer: Buffer.from(DISPLAY_STEP) });
  await expect(page.getByTestId('workbench-project-provenance')).toContainText(`Project ${PROJECT_ID} · revision 8 · 2 registered sources · 2 workbench bindings`);
  await page.getByLabel('Placement translation X mm for Donor display + validated controller').fill('150');
  await page.getByLabel('Placement translation Y mm for Donor display + validated controller').fill('0');
  await page.getByLabel('Placement translation Z mm for Donor display + validated controller').fill('0');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await page.getByRole('button', { name: 'Generate exact mesh' }).click();
  await page.getByRole('button', { name: 'Arm surface pick' }).click();
  await clickSelectedExactMesh(page);
  await expect(page.getByTestId('exact-brep-surface-anchor')).toHaveAttribute('data-anchor-id', 'anchor-balanced-cmp-display-if-display');

  const refinement = page.getByTestId('brep-mating-path-refinement-control');
  await expect(refinement).toBeVisible();
  await page.getByLabel('Adaptive refinement end translation X').fill('5');
  await page.getByLabel('Refined mating path coarse sample count').fill('6');
  await page.getByRole('button', { name: 'Refine sampled transitions' }).click();
  await expect(page.getByTestId('brep-mating-path-refinement-feedback')).toContainText('Refined 2 predicate-change brackets');
  await expect(page.getByTestId('brep-transition-bracket')).toHaveCount(2);

  expect(ingestCount).toBe(2);
  expect(bindingCount).toBe(2);
  expect(placementPersistenceRequests).toHaveLength(2);
  expect(storedMeshRequests).toHaveLength(2);
  expect(storedAnchorRequests).toHaveLength(2);
  expect(storedRefinementRequests).toHaveLength(1);
  expect(inlineCalls).toEqual([]);
});
