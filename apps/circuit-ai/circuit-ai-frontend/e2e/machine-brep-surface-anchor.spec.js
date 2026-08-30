const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const HASH = `sha256:${'b'.repeat(64)}`;
const STEP = "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n#2=CARTESIAN_POINT('',(305.,195.,12.));\nENDSEC;\nEND-ISO-10303-21;\n";

function strategyResponse(mode) {
  return {
    resource_strategy: {
      schema_version: 'resource_strategy.v1',
      strategy_mode: mode,
      coverage: {
        covered_capabilities: ['display_or_ui'],
        missing_capabilities: [],
        coverage_score: 1,
      },
      build_readiness: {
        status: 'prototype_after_evidence',
        reason: 'Surface-anchor fixture keeps the controlled display selected.',
        open_gate_count: 1,
        blocked_count: 0,
      },
      selected_resources: [
        { resource_id: 'res-display-controlled', name: 'Donor display + validated controller' },
      ],
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
        content_hash: HASH,
        byte_count: 512,
        file_schema: ['AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'],
        products: ['Donor Display Assembly'],
        units: 'mm',
        entity_count: 42,
        cartesian_point_count: 12,
        bounding_box: {
          minimum: [0, 0, 0],
          maximum: [305, 195, 12],
          size: [305, 195, 12],
          point_count: 12,
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
  const minimum = placement.translation_mm;
  const maximum = [
    minimum[0] + 305,
    minimum[1] + 195,
    minimum[2] + 12,
  ];
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
  const [x, y, z] = body.placement.translation_mm;
  const x1 = x + 305;
  const y1 = y + 195;
  const z1 = z + 12;
  const vertices = [
    [x, y, z], [x1, y, z], [x1, y1, z], [x, y1, z],
    [x, y, z1], [x1, y, z1], [x1, y1, z1], [x, y1, z1],
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

test('exact BREP mesh click becomes a hash-bound declared interface surface anchor and pose changes invalidate it', async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1600, height: 1000 });
  const anchorRequests = [];

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
    expect(body.source.content_hash).toBe(HASH);
    expect(body.source.content).toContain('ISO-10303-21');
    expect(body.placement.translation_mm).toEqual([40, -65, 10]);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(meshResponse(body)) });
  });
  await page.route('**/api/proxy/engineering/mechanical/geometry/brep/anchor', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    anchorRequests.push(body);
    expect(body.source.content_hash).toBe(HASH);
    expect(body.source.content).toContain('ISO-10303-21');
    expect(body.source.model_id).toBe('balanced-res-display-controlled');
    expect(body.placement.translation_mm).toEqual([40, -65, 10]);
    expect(body.placement.rotation_deg_xyz).toEqual([0, 0, 0]);
    expect(body.placement.authority).toBe('declared');
    expect(body.interface_id).toBe('if-display');
    expect(body.max_snap_distance_mm).toBe(5);
    expect(body.probe_point_mm).toHaveLength(3);
    body.probe_point_mm.forEach((value) => expect(Number.isFinite(value)).toBe(true));

    const probe = body.probe_point_mm;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
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
          probe_point_mm: probe,
          anchor_point_mm: probe,
          outward_normal: [0, 0, 1],
          snap_distance_mm: 0,
          max_snap_distance_mm: 5,
          face_index: 5,
          face_count: 6,
          face_geom_type: 'PLANE',
          face_area_mm2: 59475,
          face_center_mm: probe,
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
      }),
    });
  });

  await page.goto(`${APP_URL}/workbench`);
  await expect(page.getByText('live planner', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  const display = page.getByRole('button', { name: /Donor display \+ validated controller.*planner selected/i });
  await display.click();
  await page.getByLabel('Attach STEP geometry for Donor display + validated controller').setInputFiles({
    name: 'donor-display.step',
    mimeType: 'model/step',
    buffer: Buffer.from(STEP),
  });
  await expect(page.getByTestId('step-geometry-import')).toContainText('STEP envelope attached: 305 × 195 × 12 mm');
  await page.getByLabel('Placement translation X mm for Donor display + validated controller').fill('40');
  await page.getByLabel('Placement translation Y mm for Donor display + validated controller').fill('-65');
  await page.getByLabel('Placement translation Z mm for Donor display + validated controller').fill('10');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Placed in assembly: T [40, -65, 10] mm');

  await page.getByRole('button', { name: 'Generate exact mesh' }).click();
  const exactMesh = page.getByTestId('exact-brep-render-mesh');
  await expect(exactMesh).toContainText('EXACT BREP DISPLAY MESH · 12 triangles');

  const anchorControl = page.getByTestId('brep-surface-anchor-control');
  await expect(anchorControl).toBeVisible();
  await expect(page.getByLabel('BREP anchor interface for Donor display + validated controller')).toHaveValue('if-display');
  await page.getByRole('button', { name: 'Arm surface pick' }).click();
  await expect(exactMesh).toHaveAttribute('data-surface-pick-armed', 'true');
  await expect(exactMesh).toContainText('SURFACE PICK ARMED');

  // The selected exact solid is explicitly framed after tessellation and the test
  // mesh matches the declared AABB, so the canvas center intersects that solid.
  const canvas = page.locator('canvas').first();
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } });

  const feedback = page.getByTestId('brep-surface-anchor-feedback');
  await expect(feedback).toHaveAttribute('data-pick-status', 'success');
  await expect(feedback).toContainText('if-display anchored to exact BREP face 5');
  const anchor = page.getByTestId('exact-brep-surface-anchor');
  await expect(anchor).toBeVisible();
  await expect(anchor).toHaveAttribute('data-interface-id', 'if-display');
  await expect(anchor).toHaveAttribute('data-face-index', '5');
  await expect(anchor).toContainText('DECLARED BREP ANCHOR');
  await expect(anchor).toContainText('mating remains unverified');
  expect(anchorRequests).toHaveLength(1);

  // The anchor is pose-derived. Replacing the pose must clear both the exact mesh
  // and its interface anchor before the replacement placement becomes visible.
  await page.getByLabel('Placement translation X mm for Donor display + validated controller').fill('50');
  await page.getByRole('button', { name: 'Apply declared placement' }).click();
  await expect(page.getByTestId('declared-placement-editor')).toContainText('Placed in assembly: T [50, -65, 10] mm');
  await expect(page.getByTestId('exact-brep-render-mesh')).toHaveCount(0);
  await expect(page.getByTestId('exact-brep-surface-anchor')).toHaveCount(0);
  await expect(page.getByTestId('brep-surface-anchor-control')).toHaveCount(0);
});
