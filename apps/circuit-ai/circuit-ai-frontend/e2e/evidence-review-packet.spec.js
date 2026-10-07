const { test, expect } = require('@playwright/test');
const fs = require('node:fs');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const EVIDENCE = `${APP_URL}/engineering/evidence?project=outsider-fixture`;

test('the review packet downloads as a document that says what it does not establish and names the saved files by hash', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();

  const link = page.getByTestId('review-packet-link');
  await expect(link).toBeVisible();
  // It promises a report and nothing more.
  await expect(link).toHaveAttribute('title', /approves nothing/);

  const [download] = await Promise.all([page.waitForEvent('download'), link.click()]);
  expect(download.suggestedFilename()).toBe('outsider-fixture-r6-review-packet.md');
  const target = testInfo.outputPath('packet.md');
  await download.saveAs(target);
  const text = fs.readFileSync(target, 'utf8');

  expect(text.startsWith('# Review packet: Outsider DUT fixture')).toBe(true);
  expect(text).toContain('## What this packet does not establish');
  expect(text).toContain('does not open, record or imply fabrication, power-on or release authority');

  // The hashes in the document are the ones the revision recorded.
  const pin = (await (await page.request.get(`${APP_URL}/api/proxy/engineering/projects/outsider-fixture/revisions/6/artifacts`)).json()).pin.artifacts;
  expect(text).toContain(pin.schematic.sha256);
  expect(text).toContain(pin.pcb.sha256);
  // And it never reads as an approval.
  expect(text.toLowerCase()).not.toMatch(/approved for fabrication|release-ready|fabrication-ready/);
});

test('the packet link is not offered until there is a revision to report on', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.route('**/api/proxy/engineering/projects', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, projects: [] } });
  });
  await page.goto(`${APP_URL}/engineering/evidence`);
  await page.waitForTimeout(1500);
  await expect(page.getByTestId('review-packet-link')).toHaveCount(0);
});

test('the shareable version of the packet is offered next to it and carries no comments', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  const link = page.getByTestId('review-packet-share-link');
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute('title', /no comments, notes or finding text/);
  expect(await link.getAttribute('href')).toContain('include_text=false');
});

test('the version without comments leaves out what people wrote, in both forms, and the full version still has it', async ({ page }) => {
  const secret = `vendor login is violet-harbor-${Date.now()}`;
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();
  // A proposal whose reason holds something that should not be shared.
  const created = await page.request.post(`${APP_URL}/api/proxy/engineering/projects/outsider-fixture/candidates`, {
    data: { base_revision: 6, kind: 'schematic', author: 'Bob', note: secret, ops: [{ op: 'set_property', ref: 'U1', name: 'Value', value: 'violet-harbor-value' }] },
  });
  expect(created.ok()).toBe(true);

  const url = (extra) => `${APP_URL}/api/proxy/engineering/projects/outsider-fixture/review-packet?revision=6${extra}`;
  const full = await (await page.request.get(url('&format=markdown'))).text();
  expect(full).toContain(secret);

  const shared = await page.request.get(url('&format=markdown&include_text=false'));
  expect(shared.headers()['content-disposition']).toContain('-no-text.md');
  const sharedText = await shared.text();
  const sharedJson = JSON.stringify(await (await page.request.get(url('&include_text=false'))).json());
  for (const body of [sharedText, sharedJson]) {
    expect(body).not.toContain('violet-harbor');
    expect(body).not.toContain('vendor login');
    expect(body).not.toContain('outsider-fixture');
  }
  expect(shared.headers()['content-disposition']).toMatch(/filename="project-[0-9a-f]{12}-r6-/);
  expect(sharedText).toContain('are left out');
  // What is not prose is still there: the proposal exists and the files are named by hash.
  expect(sharedText).toMatch(/sha256:[0-9a-f]{64}/);
  expect(sharedText).toContain('Proposals based on this revision (');
});
