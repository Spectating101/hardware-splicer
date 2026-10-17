// The mission page, against the real backend. The agent works over the API (as it does in practice); the person
// works in the browser, with a token the script registered for this run only.
const crypto = require('node:crypto');
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
  await expect(page.getByText(/Opened as review/)).toContainText('review-');
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
