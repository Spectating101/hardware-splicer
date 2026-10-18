// The mission page, against the real backend. The agent works over the API (as it does in practice); the person
// works in the browser, with a token the script registered for this run only.
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { test, expect } = require('@playwright/test');

const APP = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const API = process.env.HS_BACKEND_URL || 'http://127.0.0.1:8000';
const TOKEN = process.env.HS_E2E_OPERATOR_TOKEN || '';
const AGENT = { kind: 'agent', id: 'e2e-agent' };

const project = `e2e-missions-${Date.now().toString(36)}`;
const snapshot = { projectId: project, projectName: 'E2E missions', currentStage: 'design', mode: 'greenfield', graph: { nodes: [], edges: [] }, machineProject: { project_id: project, name: 'E2E missions', purpose: 'e2e' } };

async function post(request, path, data, headers = {}) {
  const response = await request.post(`${API}${path}`, { data, headers });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

async function propose(request, id, event) {
  const mission = (await (await request.get(`${API}/v1/projects/${project}/missions/${id}`)).json()).mission;
  return post(request, `/v1/projects/${project}/missions/${id}/events`, { event, author: AGENT, expected_event_seq: mission.last_event_seq });
}

async function openMission(request, intake) {
  const { mission } = await post(request, `/v1/projects/${project}/missions`, { intake, author: AGENT });
  return mission.mission_id;
}

test.beforeAll(async ({ request }) => {
  const response = await request.put(`${API}/v1/projects/${project}/snapshot`, { data: { snapshot, expected_revision: 0 } });
  expect(response.ok(), await response.text()).toBeTruthy();
});

test('the person accepts a mission, the agent finishes it, and the person gets the package', async ({ page, request }) => {
  test.skip(!TOKEN, 'needs the operator token the verify script registers');
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const id = await openMission(request, { goal: 'A desk weather display from my parts', inventory: ['ESP32', 'BME280', '0.96 inch OLED'], constraints: ['Powered over USB'] });

  await page.goto(`${APP}/engineering/missions?project=${project}&mission=${id}`);
  await expect(page.getByTestId('mission-goal')).toHaveText('A desk weather display from my parts');
  await expect(page.getByTestId('verdict-title')).toHaveText('Waiting for you to accept');
  // What is and is not established is on screen from the first moment.
  await expect(page.getByLabel('What is established about the physical world')).toContainText('Not proven');
  await expect(page.getByLabel('What is established about the physical world')).toContainText('Not authorized');
  await expect(page.getByText('noted, not enforced by HS')).toBeVisible();

  // A person's token is required, and a wrong one changes nothing.
  const accept = page.getByRole('button', { name: /Accept this mission/ });
  await expect(accept).toBeDisabled();
  await page.getByPlaceholder('Paste the token you were given').fill(`wrong-${'z'.repeat(40)}`);
  await accept.click();
  await expect(page.locator('p[role="alert"]')).toContainText('not recognized');
  await expect(page.getByTestId('verdict-title')).toHaveText('Waiting for you to accept');
  await page.getByPlaceholder('Paste the token you were given').fill(TOKEN);
  await accept.click();
  await expect(page.getByTestId('verdict-title')).toHaveText('Accepted, not started');
  // The identity comes from the token, not from anything typed.
  await expect(page.getByText('You · e2e-owner')).toBeVisible();

  // The agent works over the API; the page follows without a reload.
  await propose(request, id, { type: 'candidate_proposed', candidate: { id: 'A', kind: 'clean_sheet', label: 'ESP32 + BME280 + OLED',
    spec: (await (await request.get(`${API}/v1/devices/examples`)).json()).examples.esp32_oled_bme280_usb, rationale: 'the parts as listed' } });
  for (const operation of ['device_plan', 'device_engineering']) {
    await post(request, `/v1/projects/${project}/missions/${id}/candidates/A/run`, { operation });
  }
  await propose(request, id, { type: 'terminal_proposed', state: 'READY_FOR_HUMAN_BUILD', candidate_id: 'A', reason: 'checks passed' });
  await expect(page.getByTestId('verdict-title')).toHaveText('Ready for you to build', { timeout: 20000 });
  await expect(page.getByText('HS checked this')).toBeVisible();
  await expect(page.getByText('The agent wrote')).toBeVisible();
  await expect(page.getByText('Uses every part you listed')).toBeVisible();

  // Hand-off: a ZIP whose hash is the one on screen, with honest statuses.
  await page.getByRole('button', { name: /Build the package/ }).click();
  const link = page.getByRole('link', { name: /Download ZIP/ });
  await expect(link).toBeVisible({ timeout: 30000 });
  const shown = (await page.getByText(/Package fingerprint/).textContent()).match(/[0-9a-f]{64}/)[0];
  const zip = await request.get(new URL(await link.getAttribute('href'), APP).toString());
  const bytes = await zip.body();
  expect(zip.status()).toBe(200);
  expect(bytes.subarray(0, 2).toString()).toBe('PK');
  expect(crypto.createHash('sha256').update(bytes).digest('hex')).toBe(shown);
  await expect(page.getByText('Still required')).toBeVisible();

  // Staging opens a review; the person's token names who did it.
  await page.getByRole('button', { name: /Open a review/ }).click();
  const staged = page.getByTestId('staged-review');
  await expect(staged).toContainText('review-');
  await expect(staged).toHaveAttribute('data-status', 'pending');
  const reviewId = (await staged.textContent()).match(/review-[0-9a-f]+/)[0];

  // Deciding it needs a verified person. A name in the request is not enough, from anyone.
  const decision = `${API}/v1/projects/${project}/reviews/${reviewId}/decision`;
  for (const headers of [{}, { 'X-HS-Operator-Token': `unknown-${'c'.repeat(40)}` }]) {
    const refused = await request.post(decision, { data: { decision: 'accepted', actor: 'anyone-at-all' }, headers });
    expect([401, 403]).toContain(refused.status());
  }
  await expect(staged).toHaveAttribute('data-status', 'pending');
  await page.getByRole('button', { name: /Accept into the project/ }).click();
  await expect(staged).toHaveAttribute('data-status', 'accepted');
  await expect(staged).toContainText('accepted by e2e-owner');
  expect(errors).toEqual([]);
});

test('an agent\'s own claim is shown as the agent\'s word, never as something HS checked', async ({ page, request }) => {
  const id = await openMission(request, { goal: 'A weather display', inventory: ['ESP32', 'BME280', 'OLED'] });
  await propose(request, id, { type: 'evidence_required', blocker: 'BLOCKED_UNSAFE', need: 'The regulator may overheat' });
  const mission = (await (await request.get(`${API}/v1/projects/${project}/missions/${id}`)).json()).mission;
  // An unaccepted mission can be read, and an agent's note is never presented as a request to the person.
  await page.goto(`${APP}/engineering/missions?project=${project}&mission=${id}`);
  await expect(page.getByTestId('mission-goal')).toHaveText('A weather display');
  await expect(page.getByText('Concerns the agent recorded')).toBeVisible();
  await expect(page.getByText('Asked of you')).toHaveCount(0);
  expect(mission.terminal).toBeNull();
});


test('a mission is started from a typed parts list, and the page says how each line was read first', async ({ page }) => {
  test.skip(!TOKEN, 'needs the operator token the verify script registers');
  await page.goto(`${APP}/engineering/missions?project=${project}`);
  await page.getByTestId('new-mission').click();
  await page.getByTestId('mission-goal-input').fill('A desk display for temperature, humidity and distance');
  await page.getByTestId('mission-parts-input').fill('ESP32-S3\nBME280 alongside an HC-SR04 ultrasonic\n2 OLED\nHC-SR04 ultrasonic');
  const lines = page.getByTestId('parts-reading').locator('li');
  await expect(lines).toHaveCount(4);
  // A different board, a line hiding a second part, a generic word, and a part HS has no data for.
  await expect(lines.nth(0)).toHaveAttribute('data-status', 'none');
  await expect(lines.nth(0)).toContainText('different board');
  await expect(lines.nth(1)).toHaveAttribute('data-status', 'partial');
  await expect(lines.nth(1)).toContainText('HC-SR04');
  await expect(lines.nth(2)).toHaveAttribute('data-status', 'generic');
  await expect(lines.nth(3)).toHaveAttribute('data-status', 'none');
  await expect(page.getByTestId('parts-reading')).toContainText('1 of 4 lines matched');
  await expect(page.getByTestId('parts-reading')).toContainText('nothing will be dropped');

  // It cannot be opened without a person's token, and it is signed with the token's owner.
  const open = page.getByRole('button', { name: /Open this mission/ });
  await expect(open).toBeDisabled();
  await page.getByPlaceholder('Paste the token you were given').fill(TOKEN);
  await open.click();
  await expect(page.getByTestId('mission-goal')).toHaveText('A desk display for temperature, humidity and distance');
  await expect(page.getByTestId('verdict-title')).toHaveText('Waiting for you to accept');
  await expect(page.getByText('You · e2e-owner')).toBeVisible();

  // Accepting it hands it to an agent: the page says how.
  await page.getByRole('button', { name: /Accept this mission/ }).click();
  await expect(page.getByTestId('verdict-title')).toHaveText('Accepted, not started');
  await expect(page.getByTestId('agent-handoff')).toContainText('fabrication_mission');
  await expect(page.getByTestId('agent-handoff')).toContainText(project);
});

test('a measurement request is answered by typing the reading, and an out-of-range reading stays open', async ({ page, request }) => {
  test.skip(!TOKEN, 'needs the operator token the verify script registers');
  const id = await openMission(request, { goal: 'Weather display; unsure the sensor board is 3.3 V safe', inventory: ['ESP32', 'BME280', 'OLED'] });
  await post(request, `/v1/projects/${project}/missions/${id}/accept`, {}, { 'X-HS-Operator-Token': TOKEN });
  await propose(request, id, { type: 'candidate_proposed', candidate: { id: 'A', kind: 'clean_sheet', label: 'ESP32 + BME280 + OLED',
    spec: (await (await request.get(`${API}/v1/devices/examples`)).json()).examples.esp32_oled_bme280_usb, rationale: 'the parts as listed' } });
  await propose(request, id, { type: 'evidence_required', blocker: 'BLOCKED_NEEDS_PHYSICAL_MEASUREMENT', need: 'Measure the sensor rail', candidate_id: 'A',
    request: { kind: 'electrical', target: 'the 3.3 V rail at the sensor header', quantity: 'voltage', expected: { min: 3.2, max: 3.4, unit: 'V' },
               instructions: 'With the board on USB, measure 3V3 to GND at the sensor header.' } });

  await page.goto(`${APP}/engineering/missions?project=${project}&mission=${id}`);
  await expect(page.getByTestId('verdict-title')).toHaveText('Waiting for a measurement from you');
  await expect(page.getByText('Expect: 3.2 to 3.4 V')).toBeVisible();
  const record = page.getByRole('button', { name: /Record my reading/ });
  await expect(record).toBeDisabled();

  // The wrong token is refused and nothing is recorded.
  await page.getByTestId('answer-value').fill('3.29');
  await page.getByPlaceholder('Paste the token you were given').fill(`wrong-${'z'.repeat(40)}`);
  await record.click();
  await expect(page.locator('p[role="alert"]')).toContainText('not recognized');
  await expect(page.getByTestId('verdict-title')).toHaveText('Waiting for a measurement from you');

  // A mistyped token stays in the field, so it can simply be corrected.
  await page.getByPlaceholder('Paste the token you were given').fill(TOKEN);

  // A reading outside the range is recorded, says so, and leaves the request open.
  await page.getByTestId('answer-value').fill('4.9');
  await record.click();
  await expect(page.getByTestId('contradicted-note')).toContainText('4.9 V');
  await expect(page.getByTestId('contradicted-note')).toContainText('outside what was expected');
  await expect(page.getByTestId('verdict-title')).toHaveText('Waiting for a measurement from you');

  // Measuring again inside the range answers it, and the mission goes back to work.
  await page.getByTestId('answer-value').fill('3.31');
  await record.click();
  await expect(page.getByText('You answered 3.31 V')).toBeVisible();
  await expect(page.getByTestId('verdict-title')).toHaveText('In progress');
  await expect(page.getByText('You · e2e-owner').first()).toBeVisible();
});

test('donor hardware shows how well each fact is established, and an agent finding is never a measurement', async ({ page, request }) => {
  test.skip(!TOKEN || !process.env.HS_FRONTEND_VERIFY_DIR, 'needs the operator token and the run folder the verify script provides');
  const folder = path.join(process.env.HS_FRONTEND_VERIFY_DIR, 'projects', project, 'donors', 'contracts');
  fs.mkdirSync(folder, { recursive: true });
  fs.copyFileSync(path.join(__dirname, 'fixtures', 'donor-contract-radio-buttons.json'), path.join(folder, 'donor__radio__buttons.json'));
  const id = await openMission(request, { goal: 'A weather display that reuses my old radio buttons', inventory: ['ESP32', 'BME280', 'OLED'],
    donors: [{ donor_id: 'donor:radio:buttons', label: 'Old radio buttons', optional: false }] });
  await post(request, `/v1/projects/${project}/missions/${id}/accept`, {}, { 'X-HS-Operator-Token': TOKEN });
  await propose(request, id, { type: 'finding_offered', finding: { donor_id: 'donor:radio:buttons', signal: 'KEY', method: 'vision', source: 'photo review',
    claim: 'The J1.1 trace runs to a pull-up near U3, so KEY is probably active low', artifacts: [{ name: 'radio-board-top.jpg', sha256: 'a'.repeat(64) }] } });

  await page.goto(`${APP}/engineering/missions?project=${project}&mission=${id}`);
  const donor = page.getByTestId('donor');
  await expect(donor).toHaveAttribute('data-state', 'partial');
  await expect(donor).toContainText('Old radio buttons');
  // Three facts, each only "from a document": nothing here is measured.
  await expect(donor.getByText('From a document, not measured')).toHaveCount(3);
  await expect(donor.getByText('Measured by a person', { exact: true })).toHaveCount(0);
  await expect(donor).toContainText('HS cannot generate firmware for it yet');
  await expect(donor).toContainText('Still needed before a design can rely on it');
  await expect(donor.getByText('Observed, not measured')).toBeVisible();
  await expect(donor).toContainText('never count as a measurement');
});
