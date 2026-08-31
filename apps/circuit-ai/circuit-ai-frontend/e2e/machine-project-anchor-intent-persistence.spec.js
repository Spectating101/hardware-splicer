const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const PROJECT_ID = 'durable-anchor-intent';
const HASH = `sha256:${'a'.repeat(64)}`;
const SOURCE_ID = 'registered-mainboard-step';
const RESOURCE_ID = 'res-mainboard-donor';
const ENTITY_ID = 'cmp-mainboard';
const INTERFACE_ID = 'if-display';
const PLACEMENT_ID = 'placement-balanced-res-mainboard-donor';
const ANCHOR_ID = 'anchor-balanced-cmp-mainboard-if-display';
const STEP = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(100.,80.,10.));\nENDSEC;\nEND-ISO-10303-21;\n";

function strategyResponse(mode) {
  return {
    resource_strategy: {
      schema_version: 'resource_strategy.v1',
      strategy_mode: mode,
      coverage: { covered_capabilities: ['x86_compute', 'display_or_ui'], missing_capabilities: [], coverage_score: 1 },
      build_readiness: {
        status: 'prototype_after_evidence',
        reason: 'Durable anchor fixture keeps the donor mainboard selected.',
        open_gate_count: 1,
        blocked_count: 0,
      },
      selected_resources: [{ resource_id: RESOURCE_ID, name: 'Donor x86 mainboard' }],
      blocked_resources: [],
      procurement_plan: { items: [], estimated_cost_usd: 0 },
    },
    metadata: { strategy_mode: mode },
  };
}

function geometryReport() {
  return {
    schema_version: 'hardware_splicer.mechanical_geometry_report.v1',
    project_id: PROJECT_ID,
    models: [{
      schema_version: 'hardware_splicer.step_geometry.v1',
      source_id: SOURCE_ID,
      model_id: SOURCE_ID,
      content_hash: HASH,
      byte_count: 512,
      file_schema: ['AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'],
      products: ['Donor Mainboard'],
      units: 'mm',
      entity_count: 42,
      cartesian_point_count: 8,
      bounding_box: {
        minimum: [0, 0, 0],
        maximum: [100, 80, 10],
        size: [100, 80, 10],
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

function parserRun() {
  const geometry = geometryReport();
  return {
    schema_version: 'hardware_splicer.stored_source_parser.v1',
    parser_identity: 'hardware_splicer.stored_source_parser.python.v1',
    project_id: PROJECT_ID,
    source_id: SOURCE_ID,
    content_hash: HASH,
    parser_route: 'step_geometry',
    status: 'parsed',
    authority_ceiling: 'declared',
    parsed_output: {
      step_model: geometry.models[0],
      mechanical_geometry: geometry,
      summary: { model_id: SOURCE_ID, units: 'mm', has_bounding_box: true },
    },
    derived_sources: [],
    limitations: ['Bounded STEP identity and point envelope only.'],
    raw_bytes_returned: false,
    automatic_authorization: false,
    metadata: { parser_reverified_hash: true, physical_authority_unchanged: true },
  };
}

function sourceDescriptor() {
  return {
    source_id: SOURCE_ID,
    content_hash: HASH,
    authority_ceiling: 'declared',
    metadata: {
      parser_route: 'step_geometry',
      parser_disposition: 'structured',
      original_filename: 'mainboard.step',
    },
  };
}

function bindingRow(body) {
  return {
    schema_version: 'hardware_splicer.workbench_step_binding.v1',
    candidate_id: body.candidate_id,
    resource_id: body.resource_id,
    entity_id: body.entity_id,
    source_id: body.source_id,
    model_id: body.model_id,
    content_hash: body.content_hash,
    source_materialization: 'registered_project',
    source_binding_only: true,
    physical_authority_unchanged: true,
    automatic_authorization: false,
    fabrication_authorized: false,
    power_on_authorized: false,
    motion_authorized: false,
    release_authorized: false,
  };
}

function placementRow(body) {
  return {
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
  };
}

function anchorIntentRow(body) {
  return {
    schema_version: 'hardware_splicer.workbench_brep_anchor_intent.v1',
    candidate_id: body.candidate_id,
    resource_id: body.resource_id,
    entity_id: body.entity_id,
    interface_id: body.interface_id,
    anchor_id: body.anchor_id,
    source_id: body.source_id,
    model_id: body.model_id,
    content_hash: body.content_hash,
    placement_id: body.placement_id,
    target_frame: body.target_frame,
    translation_mm: body.translation_mm,
    rotation_deg_xyz: body.rotation_deg_xyz,
    probe_point_mm: body.probe_point_mm,
    max_snap_distance_mm: body.max_snap_distance_mm,
    authority: 'declared',
    source_binding_required: true,
    durable_placement_required: true,
    registered_source_hash_reverified: true,
    kernel_result_persisted: false,
    face_identity_persisted: false,
    anchor_point_persisted: false,
    surface_normal_persisted: false,
    requires_occt_resnap_on_reopen: true,
    physical_authority_unchanged: true,
    connector_mating_verified: false,
    physical_measurement: false,
    automatic_authorization: false,
    fabrication_authorized: false,
    power_on_authorized: false,
    motion_authorized: false,
    release_authorized: false,
  };
}

function placementResponse(body) {
  const placement = body.placements[0];
  const [x, y, z] = placement.translation_mm;
  return {
    ok: true,
    clearance_boxes: [{
      object_id: placement.object_id,
      frame_id: placement.target_frame,
      minimum_mm: [x, y, z],
      maximum_mm: [x + 100, y + 80, z + 10],
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
  const [x, y, z] = body.placement.translation_mm;
  const vertices = [
    [x, y, z], [x + 100, y, z], [x + 100, y + 80, z], [x, y + 80, z],
    [x, y, z + 10], [x + 100, y, z + 10], [x + 100, y + 80, z + 10], [x, y + 80, z + 10],
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

function anchorResponse(body, faceIndex) {
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
      anchor_point_mm: [10, 0, 0],
      outward_normal: [1, 0, 0],
      snap_distance_mm: 0.05,
      max_snap_distance_mm: body.max_snap_distance_mm,
      face_index: faceIndex,
      face_count: 6,
      face_geom_type: 'PLANE',
      face_area_mm2: 800,
      face_center_mm: [10, 0, 0],
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

async function clickSelectedExactMesh(page) {
  const exactMesh = page.getByTestId('exact-brep-render-mesh');
  await expect(exactMesh).toHaveAttribute('data-surface-pick-armed', 'true');
  const canvas = page.locator('canvas').first();
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } });
  await expect(page.getByTestId('brep-surface-anchor-feedback')).toHaveAttribute('data-pick-status', 'success');
}

test('durable anchor probe intent re-snaps through stored OCCT on reload without upload replay or a second surface click', async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1600, height: 1000 });

  let projectRevision = 1;
  let projectReadCount = 0;
  let ingestCount = 0;
  let parseWriteCount = 0;
  let bindingWriteCount = 0;
  let placementWriteCount = 0;
  let placementDeriveCount = 0;
  let anchorIntentWriteCount = 0;
  const sources = [];
  const parserRuns = [];
  const bindings = [];
  const placements = [];
  const anchorIntents = [];
  const storedMeshRequests = [];
  const storedAnchorRequests = [];
  const inlineCalls = [];

  await page.route('**/api/proxy/resource/strategy', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(strategyResponse(body.strategy_mode || 'hybrid')) });
  });

  await page.route(new RegExp(`/api/proxy/engineering/projects/${PROJECT_ID}$`), async (route) => {
    projectReadCount += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        project: {
          revision: projectRevision,
          snapshot: {
            projectId: PROJECT_ID,
            projectName: 'Durable anchor intent fixture',
            engineeringSources: sources,
            engineeringSourceParserRuns: parserRuns,
            machineWorkbenchStepBindings: bindings,
            machineWorkbenchPlacements: placements,
            machineWorkbenchAnchorIntents: anchorIntents,
          },
        },
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/sources/ingest-file`, async (route) => {
    ingestCount += 1;
    expect(projectRevision).toBe(1);
    const multipart = (route.request().postDataBuffer() || Buffer.alloc(0)).toString('utf8');
    expect(multipart).toContain('mainboard.step');
    expect(multipart).toContain('\r\n\r\n1\r\n');
    const descriptor = sourceDescriptor();
    sources.push(descriptor);
    projectRevision = 2;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        project_id: PROJECT_ID,
        revision: 2,
        ingestion: {
          source_id: SOURCE_ID,
          content_hash: HASH,
          source_descriptor: descriptor,
          metadata: { raw_bytes_in_response: false },
        },
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/sources/${SOURCE_ID}/parse`, async (route) => {
    parseWriteCount += 1;
    const body = JSON.parse(route.request().postData() || '{}');
    expect(body.expected_revision).toBe(2);
    const run = parserRun();
    parserRuns.push(run);
    projectRevision = 3;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        registered: true,
        project_id: PROJECT_ID,
        revision: 3,
        parser_run: run,
        authority_unchanged: true,
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/workbench/step-bindings`, async (route) => {
    bindingWriteCount += 1;
    const body = JSON.parse(route.request().postData() || '{}');
    expect(body.expected_revision).toBe(3);
    expect(body.resource_id).toBe(RESOURCE_ID);
    const row = bindingRow(body);
    bindings.push(row);
    projectRevision = 4;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        registered: true,
        project_id: PROJECT_ID,
        revision: 4,
        workbench_step_binding: row,
        registered_source_hash_reverified: true,
        raw_registered_source_bytes_returned: false,
        physical_authority_unchanged: true,
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/workbench/placements`, async (route) => {
    placementWriteCount += 1;
    const body = JSON.parse(route.request().postData() || '{}');
    expect(body.expected_revision).toBe(4);
    expect(body.resource_id).toBe(RESOURCE_ID);
    expect(body.translation_mm).toEqual([10, 0, 0]);
    const row = placementRow(body);
    placements.push(row);
    projectRevision = 5;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        registered: true,
        project_id: PROJECT_ID,
        revision: 5,
        workbench_placement: row,
        registered_source_hash_reverified: true,
        derived_geometry_persisted: false,
        physical_authority_unchanged: true,
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/workbench/anchor-intents`, async (route) => {
    anchorIntentWriteCount += 1;
    const body = JSON.parse(route.request().postData() || '{}');
    expect(body.expected_revision).toBe(5);
    expect(body.anchor_id).toBe(ANCHOR_ID);
    expect(body.interface_id).toBe(INTERFACE_ID);
    expect(body.source_id).toBe(SOURCE_ID);
    expect(body.content_hash).toBe(HASH);
    expect(body.placement_id).toBe(PLACEMENT_ID);
    expect(body.translation_mm).toEqual([10, 0, 0]);
    expect(body.rotation_deg_xyz).toEqual([0, 0, 0]);
    expect(body.authority).toBe('declared');
    expect(body).not.toHaveProperty('face_index');
    expect(body).not.toHaveProperty('anchor_point_mm');
    expect(body).not.toHaveProperty('outward_normal');
    const row = anchorIntentRow(body);
    anchorIntents.push(row);
    projectRevision = 6;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        registered: true,
        project_id: PROJECT_ID,
        revision: 6,
        workbench_anchor_intent: row,
        registered_source_hash_reverified: true,
        kernel_result_persisted: false,
        physical_authority_unchanged: true,
      }),
    });
  });

  await page.route('**/api/proxy/engineering/mechanical/geometry/place', async (route) => {
    placementDeriveCount += 1;
    const body = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(placementResponse(body)) });
  });

  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/mesh/stored', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    storedMeshRequests.push(body);
    expect(body.project_id).toBe(PROJECT_ID);
    expect(body.source.source_id).toBe(SOURCE_ID);
    expect(body.source.content).toBeUndefined();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(meshResponse(body)) });
  });

  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/anchor/stored', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    storedAnchorRequests.push(body);
    expect(body.project_id).toBe(PROJECT_ID);
    expect(body.anchor_id).toBe(ANCHOR_ID);
    expect(body.interface_id).toBe(INTERFACE_ID);
    expect(body.source.source_id).toBe(SOURCE_ID);
    expect(body.source.content).toBeUndefined();
    expect(body.placement.translation_mm).toEqual([10, 0, 0]);
    expect(body.placement.rotation_deg_xyz).toEqual([0, 0, 0]);
    const faceIndex = storedAnchorRequests.length === 1 ? 5 : 2;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(anchorResponse(body, faceIndex)) });
  });

  for (const path of [
    'geometry/parse',
    'geometry/brep/mesh',
    'geometry/brep/anchor',
  ]) {
    await page.route(`**/api/proxy/engineering/mechanical/${path}`, async (route) => {
      inlineCalls.push(route.request().url());
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ ok: false, error: 'inline route forbidden in durable anchor test' }) });
    });
  }

  await page.goto(`${APP_URL}/workbench?project=${PROJECT_ID}`);
  await expect(page.getByText('live planner', { exact: true })).toBeVisible();
  await expect(page.getByTestId('workbench-project-provenance')).toContainText(`Project ${PROJECT_ID} · revision 1`);
  await page.getByRole('button', { name: 'Resources', exact: true }).click();

  const mainboard = page.getByRole('button', { name: /Donor x86 mainboard.*planner selected/i });
  await mainboard.click();
  await page.getByLabel('Attach STEP geometry for Donor x86 mainboard').setInputFiles({ name: 'mainboard.step', mimeType: 'model/step', buffer: Buffer.from(STEP) });
  await expect(page.getByTestId('workbench-project-provenance')).toContainText('revision 4');
  await page.getByLabel('Placement translation X mm for Donor x86 mainboard').fill('10');
  await page.getByLabel('Placement translation Y mm for Donor x86 mainboard').fill('0');
  await page.getByLabel('Placement translation Z mm for Donor x86 mainboard').fill('0');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await expect(page.getByTestId('workbench-project-provenance')).toContainText('revision 5');
  await page.getByRole('button', { name: 'Generate exact mesh' }).click();
  await expect(page.getByTestId('brep-render-mesh-control')).toContainText('registered blob hash reverified');
  await page.getByRole('button', { name: 'Arm surface pick' }).click();
  await clickSelectedExactMesh(page);
  await expect(page.getByTestId('workbench-project-provenance')).toContainText('revision 6');
  await expect(page.getByTestId('exact-brep-surface-anchor')).toHaveAttribute('data-face-index', '5');

  expect(anchorIntents).toHaveLength(1);
  expect(anchorIntents[0].kernel_result_persisted).toBe(false);
  expect(anchorIntents[0].face_identity_persisted).toBe(false);
  expect(anchorIntents[0].surface_normal_persisted).toBe(false);
  expect(anchorIntents[0].requires_occt_resnap_on_reopen).toBe(true);
  expect(anchorIntents[0]).not.toHaveProperty('face_index');
  expect(anchorIntents[0]).not.toHaveProperty('anchor_point_mm');
  expect(anchorIntents[0]).not.toHaveProperty('outward_normal');
  expect(storedAnchorRequests).toHaveLength(1);
  expect(storedMeshRequests).toHaveLength(1);
  expect(inlineCalls).toEqual([]);

  await page.reload();
  await expect(page.getByText('live planner', { exact: true })).toBeVisible();
  await expect(page.getByTestId('workbench-project-provenance')).toContainText(`Project ${PROJECT_ID} · revision 6 · 1 registered source · 1 workbench binding`);
  await expect.poll(() => storedAnchorRequests.length).toBe(2);
  expect(storedAnchorRequests[1].probe_point_mm).toEqual(anchorIntents[0].probe_point_mm);
  expect(storedAnchorRequests[1].source.content).toBeUndefined();
  expect(ingestCount).toBe(1);
  expect(parseWriteCount).toBe(1);
  expect(bindingWriteCount).toBe(1);
  expect(placementWriteCount).toBe(1);
  expect(anchorIntentWriteCount).toBe(1);
  expect(projectRevision).toBe(6);
  expect(projectReadCount).toBeGreaterThanOrEqual(3);
  await expect.poll(() => placementDeriveCount).toBe(2);

  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await mainboard.click();
  await expect(page.getByLabel('Placement translation X mm for Donor x86 mainboard')).toHaveValue('10');
  await expect(page.getByRole('button', { name: 'Generate exact mesh' })).toBeVisible();
  await expect(page.getByTestId('exact-brep-render-mesh')).toHaveCount(0);

  // Derived tessellation is intentionally absent after reload. Once regenerated from
  // the registered blob, the already re-snapped anchor appears without arming or
  // clicking the surface a second time.
  await page.getByRole('button', { name: 'Generate exact mesh' }).click();
  await expect(page.getByTestId('brep-render-mesh-control')).toContainText('registered blob hash reverified');
  await expect(page.getByTestId('exact-brep-surface-anchor')).toHaveAttribute('data-face-index', '2');
  expect(storedMeshRequests).toHaveLength(2);
  expect(storedAnchorRequests).toHaveLength(2);
  expect(anchorIntentWriteCount).toBe(1);
  expect(ingestCount).toBe(1);
  expect(inlineCalls).toEqual([]);
});
