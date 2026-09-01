const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test.setTimeout(75_000);

test('reuse mission turns donor evidence, resolve actions, operator facts, and strategy choices into canonical workbench state', async ({ page }, testInfo) => {
  const plannerPayloads = [];
  const fieldAgentPayloads = [];

  await page.route('**/api/proxy/analyze', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        results: {
          detections: [{ class_name: 'cooling fan', confidence: 0.91, bbox: [0, 0, 20, 20] }],
          functionality_data: {
            components: [{
              id: 'fan-assembly-1',
              type: 'cooling fan',
              description: 'Observed donor cooling fan',
              capabilities: ['fan_or_pump', 'motor_or_load'],
              reuse_value: 'high',
              market_value: 0,
              educational_value: 'medium',
            }],
            capabilities: ['fan_or_pump', 'motor_or_load'],
          },
        },
        summary: { confidence_score: 0.91 },
      }),
    });
  });

  await page.route('**/api/proxy/resource/strategy', async (route) => {
    const payload = route.request().postDataJSON();
    plannerPayloads.push(payload);
    const available = Array.isArray(payload.available_resources) ? payload.available_resources : [];
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        resource_strategy: {
          schema_version: 'resource_strategy.v1',
          strategy_mode: payload.strategy_mode,
          build_readiness: {
            status: 'needs_evidence',
            reason: 'Candidate uses provisional donor evidence and remains gated.',
            open_gate_count: payload.strategy_mode === 'constrained' ? 5 : payload.strategy_mode === 'open_procurement' ? 1 : 3,
          },
          coverage: { coverage_score: 0.82, missing_capabilities: [] },
          procurement_plan: { items: [], estimated_cost_usd: 0 },
          selected_resources: available,
          blocked_resources: [],
        },
      }),
    });
  });

  await page.route('**/api/proxy/hardware/field-agent/next-action', async (route) => {
    const payload = route.request().postDataJSON();
    fieldAgentPayloads.push(payload);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        field_operator: {
          schema_version: 'hardware_field_operator_next_action.v1',
          available: true,
          operational_call: {
            action_id: 'capture_topology_or_supply_netlist',
            action_type: 'capture_or_measurement',
            priority: 2,
            authority: 'operational_advisory',
            summary: 'Capture measured topology or supply a versioned simulation netlist.',
            why: 'The test kit cannot simulate without topology/netlist evidence.',
            tools: ['DMM continuity mode', 'close-up camera'],
            procedure: [
              'Photograph connector markings and likely rail labels.',
              'Measure ground continuity and power-to-ground no-short.',
              'Measure rail voltage and polarity under current limit.',
            ],
          },
        },
      }),
    });
  });

  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto(`${APP_URL}/workbench/mission`);

  await expect(page.getByRole('heading', { name: 'Turn available hardware into a defensible build.', level: 1 })).toBeVisible();
  await expect(page.getByText('Portable Linux workstation', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Reuse mission stages')).toContainText('Inventory');
  await expect(page.getByLabel('Reuse mission stages')).toContainText('Build');
  await expect(page.getByRole('heading', { name: 'Photograph a donor item before you know exactly what it is.', level: 2 })).toBeVisible();

  await page.getByLabel('Analyze donor photo').setInputFiles({
    name: 'printer-donor.png',
    mimeType: 'image/png',
    buffer: Buffer.from('89504e470d0a1a0a', 'hex'),
  });
  await expect(page.getByText('Observed donor cooling fan', { exact: true })).toBeVisible();
  await expect(page.getByText('91% observed', { exact: true })).toBeVisible();
  await expect(page.getByText(/1 provisional resource added/)).toBeVisible();

  const maxReuse = page.getByRole('button', { name: /Maximum reuse/ });
  await maxReuse.click();
  await expect(maxReuse).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Resolve 5 blocking gates' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Build package' })).toBeDisabled();
  await expect(page.getByLabel('Practical evidence closures')).toContainText('Do the next useful observation, measurement or fit check.');
  await page.screenshot({ path: testInfo.outputPath('reuse-mission-overview.png') });

  // A generic gate is now a concrete operator action focused on the exact donor resource.
  await page.getByRole('button', { name: 'Resolve Confirm Observed donor cooling fan' }).click();
  await expect(page).toHaveURL(/\/workbench\?stage=resolve&candidate=max-reuse&resource=photo-printer-donor-png-fan-assembly-1-1$/);
  await expect(page.getByRole('heading', { name: 'Portable Linux workstation', level: 1 })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Resources', exact: true })).toBeVisible();
  await expect(page.getByTestId('focused-donor-resource')).toContainText('Resolve · Observed donor cooling fan');
  await expect(page.getByTestId('workbench-donor-evidence')).toContainText('Donor evidence worksheet');
  await expect(page.getByTestId('field-agent-action')).toContainText('Capture measured topology or supply a versioned simulation netlist.');

  // Operator facts are stored, but remain explicitly non-authoritative, then feed the field-agent context.
  await page.getByLabel('Model / marking actually observed').fill('DF1208SL donor label');
  await page.getByLabel('Visible condition').selectOption('appears_usable');
  await page.getByLabel('Evidence URI / note source').fill('photo://printer-donor/fan-label');
  await page.getByLabel('Dimensions / fit observation').fill('80 x 80 x 15 mm measured with caliper');
  await page.getByLabel('Connector / interface observation').fill('2-pin JST-like plug; pinout unverified');
  await page.getByLabel('Power observation').fill('12 V marking visible; current not yet measured');
  await page.getByLabel('Operator notes').fill('No visible cracked housing; dust present.');
  await page.getByRole('button', { name: 'Save observation' }).click();
  await expect(page.getByTestId('workbench-donor-evidence')).toContainText('operator claim');
  await expect(page.getByTestId('workbench-donor-evidence')).toContainText('Typed observations are not topology measurements');

  await expect.poll(() => fieldAgentPayloads.length).toBeGreaterThanOrEqual(2);
  expect(fieldAgentPayloads.some((payload) => (
    Array.isArray(payload.photo_observations)
    && payload.photo_observations.some((row) => row.resource_id === 'photo-printer-donor-png-fan-assembly-1-1')
    && payload.operator_notes?.identity_label === 'DF1208SL donor label'
    && payload.operator_notes?.condition === 'appears_usable'
    && payload.operator_notes?.authority === 'operator_claim'
    && payload.operator_notes?.power_note === '12 V marking visible; current not yet measured'
  ))).toBeTruthy();

  // The same provisional resource survives back into ordinary inventory and real resource planning.
  await page.goto(`${APP_URL}/workbench/mission`);
  await expect(page.getByText('Observed donor cooling fan', { exact: true })).toBeVisible();
  const maxReuseAgain = page.getByRole('button', { name: /Maximum reuse/ });
  await maxReuseAgain.click();
  await page.getByRole('button', { name: 'Review available hardware' }).click();
  await expect(page).toHaveURL(/\/workbench\?stage=inventory&candidate=max-reuse$/);
  await expect(page.getByText(/Build blocked · 5 gates/)).toBeVisible();
  await expect(page.getByText('Unknown old lithium pack', { exact: true })).toBeVisible();
  await expect(page.getByTestId('workbench-donor-session')).toContainText('1 provisional donor resource');

  await expect.poll(() => plannerPayloads.length).toBeGreaterThanOrEqual(3);
  expect(plannerPayloads.some((payload) => (
    Array.isArray(payload.available_resources)
    && payload.available_resources.some((resource) => (
      resource.resource_id === 'photo-printer-donor-png-fan-assembly-1-1'
      && resource.resource_kind === 'salvaged'
      && resource.evidence_status === 'needs_evidence'
      && resource.capabilities.includes('fan_or_pump')
    ))
  ))).toBeTruthy();

  // The worksheet persists when the exact donor is focused again.
  await page.goto(`${APP_URL}/workbench?stage=resolve&candidate=max-reuse&resource=photo-printer-donor-png-fan-assembly-1-1`);
  await expect(page.getByLabel('Model / marking actually observed')).toHaveValue('DF1208SL donor label');
  await expect(page.getByLabel('Visible condition')).toHaveValue('appears_usable');
  await expect(page.getByLabel('Power observation')).toHaveValue('12 V marking visible; current not yet measured');

  await page.goto(`${APP_URL}/workbench/mission`);
  await expect(page.getByText('Observed donor cooling fan', { exact: true })).toBeVisible();
  const lowRisk = page.getByRole('button', { name: /Lowest integration risk/ });
  await lowRisk.click();
  await expect(lowRisk).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByLabel('Practical evidence closures')).toContainText('Measure the whole-machine power envelope');
  await page.getByRole('button', { name: 'Open engineering verification' }).click();
  await expect(page).toHaveURL(/\/workbench\?stage=verify&candidate=low-risk$/);
  await expect(page.getByRole('heading', { name: 'DECK-001', level: 1 })).toBeVisible();
  await expect(page.getByText('Machine tree', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Verification', exact: true })).toBeVisible();
  await expect(page.getByTestId('workbench-donor-session')).toContainText('Photo-derived observations affect candidate planning only');
});
