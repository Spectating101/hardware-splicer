const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const PROJECT_ID = 'durable-scene';
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
        reason: 'Durable scene fixture keeps both donor resources selected.',
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

function parserRun(sourceId) {
  const config = sourceConfig(sourceId);
  return {
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

function sourceDescriptor(sourceId, filename) {
  const config = sourceConfig(sourceId);
  return {
    source_id: sourceId,
    content_hash: config.hash,
    authority_ceiling: 'declared',
    metadata: {
      parser_route: 'step_geometry',
      parser_disposition: 'structured',
      original_filename: filename,
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

function upsertByResource(rows, row) {
  const index = rows.findIndex((value) => value.candidate_id === row.candidate_id && value.resource_id === row.resource_id);
  if (index >= 0) rows[index] = row;
  else rows.push(row);
}

test('project-bound declared placements are revisioned, re-derived on reload, and never persist derived exact evidence', async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1600, height: 1000 });

  let projectRevision = 1;
  let projectReadCount = 0;
  let ingestCount = 0;
  let parseCount = 0;
  let bindingCount = 0;
  let placementWriteCount = 0;
  let placementClearCount = 0;
  let placementDeriveCount = 0;
  const sources = [];
  const parserRuns = [];
  const bindings = [];
  const placements = [];
  const storedMeshRequests = [];
  const inlineMeshCalls = [];

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
            projectName: 'Durable scene fixture',
            engineeringSources: sources,
            engineeringSourceParserRuns: parserRuns,
            machineWorkbenchStepBindings: bindings,
            machineWorkbenchPlacements: placements,
          },
        },
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/sources/ingest-file`, async (route) => {
    ingestCount += 1;
    const multipart = (route.request().postDataBuffer() || Buffer.alloc(0)).toString('utf8');
    const mainboard = multipart.includes('mainboard.step');
    const expectedRevision = mainboard ? 1 : 5;
    expect(projectRevision).toBe(expectedRevision);
    expect(multipart).toContain(`\r\n\r\n${expectedRevision}\r\n`);
    const sourceId = mainboard ? MAINBOARD_SOURCE : DISPLAY_SOURCE;
    const descriptor = sourceDescriptor(sourceId, mainboard ? 'mainboard.step' : 'display.step');
    sources.push(descriptor);
    projectRevision += 1;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        project_id: PROJECT_ID,
        revision: projectRevision,
        ingestion: {
          source_id: sourceId,
          content_hash: descriptor.content_hash,
          source_descriptor: descriptor,
          metadata: { raw_bytes_in_response: false },
        },
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/sources/*/parse`, async (route) => {
    parseCount += 1;
    const url = new URL(route.request().url());
    const sourceId = decodeURIComponent(url.pathname.split('/sources/')[1].split('/parse')[0]);
    const body = JSON.parse(route.request().postData() || '{}');
    expect(body.expected_revision).toBe(projectRevision);
    const run = parserRun(sourceId);
    parserRuns.push(run);
    projectRevision += 1;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        registered: true,
        project_id: PROJECT_ID,
        revision: projectRevision,
        parser_run: run,
        authority_unchanged: true,
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/workbench/step-bindings`, async (route) => {
    bindingCount += 1;
    const body = JSON.parse(route.request().postData() || '{}');
    expect(body.expected_revision).toBe(projectRevision);
    const row = bindingRow(body);
    upsertByResource(bindings, row);
    projectRevision += 1;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        registered: true,
        project_id: PROJECT_ID,
        revision: projectRevision,
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
    expect(body.expected_revision).toBe(projectRevision);
    expect(body.authority).toBe('declared');
    expect(body.target_frame).toBe('assembly');
    expect(body.content_hash).toBe(body.source_id === MAINBOARD_SOURCE ? HASH_A : HASH_B);
    const row = placementRow(body);
    upsertByResource(placements, row);
    projectRevision += 1;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        registered: true,
        project_id: PROJECT_ID,
        revision: projectRevision,
        workbench_placement: row,
        registered_source_hash_reverified: true,
        derived_geometry_persisted: false,
        physical_authority_unchanged: true,
      }),
    });
  });

  await page.route(`**/api/proxy/engineering/projects/${PROJECT_ID}/workbench/placements/clear`, async (route) => {
    placementClearCount += 1;
    const body = JSON.parse(route.request().postData() || '{}');
    expect(body.expected_revision).toBe(projectRevision);
    const index = placements.findIndex((row) => row.candidate_id === body.candidate_id && row.resource_id === body.resource_id);
    expect(index).toBeGreaterThanOrEqual(0);
    expect(placements[index].placement_id).toBe(body.placement_id);
    expect(placements[index].content_hash).toBe(body.content_hash);
    placements.splice(index, 1);
    projectRevision += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        cleared: true,
        project_id: PROJECT_ID,
        revision: projectRevision,
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
    expect(body.source.content).toBeUndefined();
    expect(body.source.model_id).toBe(body.source.source_id);
    expect([MAINBOARD_SOURCE, DISPLAY_SOURCE]).toContain(body.source.source_id);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(meshResponse(body)) });
  });

  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/mesh', async (route) => {
    inlineMeshCalls.push(route.request().url());
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ ok: false, error: 'inline mesh forbidden for durable scene' }) });
  });

  await page.goto(`${APP_URL}/workbench?project=${PROJECT_ID}`);
  await expect(page.getByText('live planner', { exact: true })).toBeVisible();
  await expect(page.getByTestId('workbench-project-provenance')).toContainText(`Project ${PROJECT_ID} · revision 1`);
  await page.getByRole('button', { name: 'Resources', exact: true }).click();

  const mainboard = page.getByRole('button', { name: /Donor x86 mainboard.*planner selected/i });
  await mainboard.click();
  await page.getByLabel('Attach STEP geometry for Donor x86 mainboard').setInputFiles({ name: 'mainboard.step', mimeType: 'model/step', buffer: Buffer.from(MAINBOARD_STEP) });
  await expect(page.getByTestId('workbench-project-provenance')).toContainText('revision 4');
  await page.getByLabel('Placement translation X mm for Donor x86 mainboard').fill('10');
  await page.getByLabel('Placement translation Y mm for Donor x86 mainboard').fill('0');
  await page.getByLabel('Placement translation Z mm for Donor x86 mainboard').fill('0');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await expect(page.getByTestId('workbench-project-provenance')).toContainText('revision 5');
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Source-bound transform persisted at project revision 5');

  const display = page.getByRole('button', { name: /Donor display \+ validated controller.*planner selected/i });
  await display.click();
  await page.getByLabel('Attach STEP geometry for Donor display + validated controller').setInputFiles({ name: 'display.step', mimeType: 'model/step', buffer: Buffer.from(DISPLAY_STEP) });
  await expect(page.getByTestId('workbench-project-provenance')).toContainText('revision 8');
  await page.getByLabel('Placement translation X mm for Donor display + validated controller').fill('150');
  await page.getByLabel('Placement translation Y mm for Donor display + validated controller').fill('0');
  await page.getByLabel('Placement translation Z mm for Donor display + validated controller').fill('0');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await expect(page.getByTestId('workbench-project-provenance')).toContainText(`Project ${PROJECT_ID} · revision 9 · 2 registered sources · 2 workbench bindings`);
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Source-bound transform persisted at project revision 9');

  await page.getByRole('button', { name: 'Generate exact mesh' }).click();
  await expect(page.getByTestId('brep-render-mesh-control')).toContainText('registered blob hash reverified');
  expect(storedMeshRequests).toHaveLength(1);
  expect(inlineMeshCalls).toEqual([]);

  expect(projectRevision).toBe(9);
  expect(ingestCount).toBe(2);
  expect(parseCount).toBe(2);
  expect(bindingCount).toBe(2);
  expect(placementWriteCount).toBe(2);
  expect(placementDeriveCount).toBe(2);
  expect(placements).toHaveLength(2);
  expect(placements.every((row) => row.derived_geometry_persisted === false)).toBe(true);
  expect(placements.some((row) => Object.prototype.hasOwnProperty.call(row, 'minimum_mm'))).toBe(false);
  expect(placements.some((row) => Object.prototype.hasOwnProperty.call(row, 'vertices_mm'))).toBe(false);

  // Full reload must consume only the durable project snapshot. No ingest, parser,
  // occurrence-binding, mesh, anchor or other derived evidence is silently replayed.
  await page.reload();
  await expect(page.getByText('live planner', { exact: true })).toBeVisible();
  await expect(page.getByTestId('workbench-project-provenance')).toContainText(`Project ${PROJECT_ID} · revision 9 · 2 registered sources · 2 workbench bindings`);
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  expect(projectReadCount).toBeGreaterThanOrEqual(2);
  await expect.poll(() => placementDeriveCount).toBe(4);
  expect(ingestCount).toBe(2);
  expect(parseCount).toBe(2);
  expect(bindingCount).toBe(2);
  expect(placementWriteCount).toBe(2);
  expect(storedMeshRequests).toHaveLength(1);

  await mainboard.click();
  await expect(page.getByLabel('Placement translation X mm for Donor x86 mainboard')).toHaveValue('10');
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Placed in assembly: T [10, 0, 0] mm');
  await expect(page.getByTestId('brep-render-mesh-control')).toContainText('registered server-side STEP blob');

  await display.click();
  await expect(page.getByLabel('Placement translation X mm for Donor display + validated controller')).toHaveValue('150');
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Placed in assembly: T [150, 0, 0] mm');
  await expect(page.getByRole('button', { name: 'Generate exact mesh' })).toBeVisible();
  await expect(page.getByTestId('exact-brep-render-mesh')).toHaveCount(0);

  // Exact tessellation is deliberately not persisted. It can be regenerated from
  // the registered blob after reload without any raw STEP replay into the browser.
  await page.getByRole('button', { name: 'Generate exact mesh' }).click();
  await expect(page.getByTestId('brep-render-mesh-control')).toContainText('registered blob hash reverified');
  expect(storedMeshRequests).toHaveLength(2);
  expect(inlineMeshCalls).toEqual([]);

  await page.getByLabel('Clear declared placement for Donor display + validated controller').click();
  await expect(page.getByTestId('workbench-project-provenance')).toContainText('revision 10');
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Declared placement cleared at project revision 10');
  expect(placementClearCount).toBe(1);
  expect(projectRevision).toBe(10);
  expect(placements).toHaveLength(1);
  expect(placements[0].resource_id).toBe('res-mainboard-donor');
  expect(inlineMeshCalls).toEqual([]);
});
