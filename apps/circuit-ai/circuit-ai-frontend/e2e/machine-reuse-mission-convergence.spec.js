const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test.setTimeout(75_000);

test('reuse mission closes the loop from donor photo through operator facts and trusted bench capture', async ({ page }, testInfo) => {
  const plannerPayloads = [];
  const fieldAgentPayloads = [];
  const measurementPayloads = [];

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

  await page.route('**/api/proxy/hardware/measurement-session/progress', async (route) => {
    const payload = route.request().postDataJSON();
    measurementPayloads.push(payload);
    const measurements = payload.bench_topology_capture?.measurements || [];
    const closed = measurements.length;
    const required = [
      { kind: 'resistance', target: 'power to ground no-short', unit: 'ohm', notes: 'Unpowered resistance check between supply and ground.' },
      { kind: 'continuity', target: 'connector ground to exposed ground', unit: '', notes: 'Confirm common ground reference.' },
      { kind: 'voltage', target: 'input voltage and polarity', unit: 'V', notes: 'Measure supply rail voltage and polarity under current limit.' },
      { kind: 'current', target: 'current draw under current-limited supply', unit: 'A', notes: 'Record first-power current at a safe current limit.' },
      { kind: 'thermal', target: 'thermal behavior after first power', unit: 'C', notes: 'Record no abnormal heating after first power.' },
    ];
    const next = required[Math.min(closed, required.length - 1)];
    const requiredMeasurements = required.map((row, index) => ({
      requirement_id: `required_${index + 1}`,
      ...row,
      status: index < closed ? 'pass' : 'open',
      submitted_measurement_id: index < closed ? measurements[index]?.measurement_id : null,
    }));
    const sessionStatus = closed > 0 ? 'measurement_in_progress' : 'waiting_for_measurements';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        measurement_session_progress: {
          mode: 'measurement_session_progress',
          schema_version: 'measurement_session_progress.v1',
          available: true,
          status: sessionStatus,
          progress: {
            schema_version: 'measurement_session_progress_summary.v1',
            required_count: required.length,
            closed_count: closed,
            open_count: Math.max(required.length - closed, 0),
            failed_count: 0,
            submitted_count: closed,
            unmatched_submitted_count: 0,
            progress_score: closed / required.length,
            capture_verdict: closed > 0 ? 'measurement_capture_incomplete' : 'measurement_capture_required',
            authority_packet_ready: false,
            template_complete: false,
          },
          next_measurement: {
            action_id: `record_${next.kind}`,
            kind: next.kind,
            target: next.target,
            unit: next.unit,
            prompt: next.notes,
          },
          required_measurements: requiredMeasurements,
          submitted_measurements: measurements,
          capture_integrity: {
            schema_version: 'measurement_capture_integrity.v1',
            verdict: closed > 0 ? 'measurement_capture_incomplete' : 'measurement_capture_required',
            trusted_root_provenance: closed > 0,
            missing_measurement_categories: closed > 0 ? ['continuity', 'voltage', 'current', 'thermal'] : ['resistance', 'continuity', 'voltage', 'current', 'thermal'],
          },
          authority_closure: {
            schema_version: 'measurement_authority_closure.v1',
            authority_after: {
              current_authority_level: closed > 0 ? 'measured_partial' : 'visual_candidate',
              can: { use_measured_pinout: false, claim_production_repair_release: false },
            },
          },
          claim_boundary: 'Session progress does not authorize power, splice, or repair.',
        },
        metadata: {
          status: sessionStatus,
          open_count: Math.max(required.length - closed, 0),
          authority_packet_ready: false,
          next_action_id: `record_${next.kind}`,
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

  await page.getByRole('button', { name: 'Resolve Confirm Observed donor cooling fan' }).click();
  await expect(page).toHaveURL(/\/workbench\?stage=resolve&candidate=max-reuse&resource=photo-printer-donor-png-fan-assembly-1-1$/);
  await expect(page.getByRole('heading', { name: 'Portable Linux workstation', level: 1 })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Resources', exact: true })).toBeVisible();
  await expect(page.getByTestId('focused-donor-resource')).toContainText('Resolve · Observed donor cooling fan');
  await expect(page.getByTestId('workbench-donor-evidence')).toContainText('Donor evidence worksheet');
  await expect(page.getByTestId('field-agent-action')).toContainText('Capture measured topology or supply a versioned simulation netlist.');

  // Operator observations stay claims and feed field guidance, but not measurement authority.
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

  // The backend's measurement-session template now drives the next trusted reading.
  const bench = page.getByTestId('donor-bench-capture');
  await expect(bench).toContainText('Trusted bench capture');
  await expect(page.getByTestId('next-bench-measurement')).toContainText('power to ground no-short');
  await bench.getByLabel('Operator ID').fill('bench-operator-1');
  await bench.getByLabel('Evidence URI', { exact: true }).fill('bench://printer-donor/fan/no-short-001');
  await bench.getByLabel('Instrument ID').fill('dmm-cal-01');
  await bench.getByLabel('Instrument type').selectOption('calibrated_dmm');
  await bench.getByLabel('Calibration').selectOption('valid');
  await bench.getByLabel('Result status').selectOption('pass');
  await bench.getByLabel('Value').fill('pass');
  await bench.getByLabel('Measurement note').fill('Unpowered check, fan disconnected from donor supply.');
  await bench.getByRole('button', { name: 'Add trusted reading' }).click();
  await expect(page.getByTestId('bench-measurement-list')).toContainText('resistance · power to ground no-short');
  await expect(bench).toContainText('1 closed · 4 open · measurement_in_progress');
  await expect(page.getByTestId('next-bench-measurement')).toContainText('connector ground to exposed ground');
  await expect(bench).toContainText('measurement_capture_incomplete');
  await expect(bench).toContainText('measured_partial');

  await expect.poll(() => measurementPayloads.length).toBeGreaterThanOrEqual(2);
  expect(measurementPayloads.some((payload) => {
    const capture = payload.bench_topology_capture;
    const measurement = capture?.measurements?.[0];
    return capture?.schema_version === 'bench_topology_capture.v1'
      && capture?.operator_id === 'bench-operator-1'
      && capture?.instruments?.some((instrument) => (
        instrument.instrument_id === 'dmm-cal-01'
        && instrument.instrument_type === 'calibrated_dmm'
        && instrument.calibration_status === 'valid'
      ))
      && capture?.artifacts?.some((artifact) => artifact.uri === 'bench://printer-donor/fan/no-short-001')
      && measurement?.kind === 'resistance'
      && measurement?.target === 'power to ground no-short'
      && measurement?.status === 'pass'
      && measurement?.instrument_id === 'dmm-cal-01'
      && measurement?.evidence_uri === 'bench://printer-donor/fan/no-short-001';
  })).toBeTruthy();

  // Provisional inventory and trusted bench capture survive navigation independently.
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

  await page.goto(`${APP_URL}/workbench?stage=resolve&candidate=max-reuse&resource=photo-printer-donor-png-fan-assembly-1-1`);
  await expect(page.getByLabel('Model / marking actually observed')).toHaveValue('DF1208SL donor label');
  await expect(page.getByLabel('Visible condition')).toHaveValue('appears_usable');
  await expect(page.getByLabel('Power observation')).toHaveValue('12 V marking visible; current not yet measured');
  await expect(page.getByTestId('bench-measurement-list')).toContainText('resistance · power to ground no-short');
  await expect(page.getByTestId('next-bench-measurement')).toContainText('connector ground to exposed ground');

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
