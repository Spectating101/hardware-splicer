const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const EVIDENCE = `${APP_URL}/engineering/evidence?project=outsider-fixture`;

// Screen position of a placed schematic symbol, from the viewer's own camera, so the click lands on the part
// regardless of the surrounding layout. KiCanvas fits its camera after loading, so wait until the point stops moving.
async function symbolScreenPoint(page, reference) {
  const read = () => page.evaluate((ref) => {
    const viewer = document.querySelector('kicanvas-embed:not([data-retired])').shadowRoot.querySelector('kc-schematic-app').viewer;
    const symbols = Array.from(viewer.schematic.symbols.values ? viewer.schematic.symbols.values() : viewer.schematic.symbols);
    const symbol = symbols.find((item) => item.reference === ref);
    const point = viewer.viewport.camera.world_to_screen({ x: symbol.at.position.x, y: symbol.at.position.y });
    const rect = viewer.canvas.getBoundingClientRect();
    return { x: point.x + rect.left, y: point.y + rect.top };
  }, reference);
  let previous = await read();
  for (let attempt = 0; attempt < 40; attempt += 1) {
    await page.waitForTimeout(150);
    const next = await read();
    if (Math.abs(next.x - previous.x) < 0.5 && Math.abs(next.y - previous.y) < 0.5) return next;
    previous = next;
  }
  return previous;
}

test('parts tab lists the design BOM, flags a missing MPN, and checks nothing until asked', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await page.getByRole('button', { name: /^Parts/ }).click();

  const panel = page.getByTestId('parts-panel');
  await expect(panel.getByText(/components in .* lines/)).toBeVisible();
  await expect(panel.getByText('TXU0304PWR').first()).toBeVisible();
  await expect(panel.getByText('No MPN in the design').first()).toBeVisible();
  await expect(panel.getByText('Availability not checked').first()).toBeVisible();

  // Asking for availability when no provider is enabled says so instead of inventing stock.
  await panel.getByRole('button', { name: 'Check availability' }).click();
  await expect(panel.getByText('no providers enabled')).toBeVisible();
  await expect(panel.getByText(/in stock/)).toHaveCount(0);
});

test('3D tab renders the retained board and Schematic still works afterwards', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await page.getByRole('button', { name: '3D', exact: true }).click();

  const model = page.getByTestId('model3d');
  await expect(model).toBeVisible();
  await expect(model.locator('canvas')).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole('button', { name: 'Edit', exact: true })).toHaveCount(0);

  await page.getByRole('button', { name: 'Schematic', exact: true }).click();
  await expect(page.locator('kicanvas-embed:not([data-retired])')).toHaveCount(1);
  await expect(model).toHaveCount(0);
});

test('two reviewers see each other and a new thread arrives without a reload', async ({ browser }) => {
  const alice = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const bob = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await alice.addInitScript(() => localStorage.setItem('hs-review-author', 'Alice'));
  await bob.addInitScript(() => localStorage.setItem('hs-review-author', 'Bob'));
  await alice.goto(EVIDENCE);
  await bob.goto(EVIDENCE);

  await expect(alice.getByTestId('presence')).toHaveAttribute('title', /Bob/, { timeout: 20000 });
  await alice.getByRole('button', { name: 'Threads', exact: true }).click();
  await bob.getByRole('button', { name: 'Threads', exact: true }).click();

  const body = `Live comment ${Date.now()}`;
  await bob.locator('#new-thread-body').fill(body);
  await bob.getByRole('button', { name: 'Start thread' }).click();
  // Alice never reloads: the comment reaches her through the change stream, once.
  await expect(alice.getByText(body)).toHaveCount(1, { timeout: 10000 });
});

test('a drafted edit becomes a proposal that is previewed but never applied', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.addInitScript(() => localStorage.setItem('hs-review-author', 'Alice'));
  await page.goto(EVIDENCE);
  await expect(page.locator('kicanvas-embed:not([data-retired])')).toHaveCount(1);
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByTestId('edit-dock')).toContainText('Select a part');
  await expect(page.getByText('Drafting a proposal')).toBeVisible();

  await page.waitForFunction(() => {
    const app = document.querySelector('kicanvas-embed:not([data-retired])')?.shadowRoot?.querySelector('kc-schematic-app');
    return Boolean(app && app.viewer && app.viewer.schematic && app.viewer.canvas);
  });
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });

  const reason = `Turn U1 ${Date.now()}`;
  await page.getByRole('button', { name: 'Rotate 90 degrees clockwise' }).click();
  await page.getByLabel('Reason for the proposal').fill(reason);
  await page.getByRole('button', { name: /^Propose 1 change/ }).click();

  const panel = page.getByTestId('proposals-panel');
  // Found by its own reason: earlier runs against a long-lived fixture backend may have left other proposals, and a
  // live update can reorder the list.
  const newest = panel.getByTestId('proposal-card').filter({ hasText: reason });
  await expect(newest.getByText(`“${reason}”`)).toBeVisible({ timeout: 15000 });
  await expect(newest.getByText('Not applied')).toBeVisible({ timeout: 15000 });
  await expect(newest.getByText(/rotate U1/)).toBeVisible();
  await expect(newest.getByText(/does not accept or reject anything/)).toBeVisible();

  await newest.getByRole('button', { name: 'Preview with changes marked' }).click();
  await expect(page.getByText(/Proposal preview/i)).toBeVisible();
  // The changed part is boxed on the proposed file, and a listed change can be clicked to find it.
  await expect(page.getByTestId('diff-highlight').first()).toBeVisible({ timeout: 10000 });
  await newest.getByRole('button', { name: /U1/ }).first().click();
  await expect(page.getByTestId('diff-highlight-label')).toContainText('U1');
  // Previewing never offers editing, and the retained revision is still the one on record.
  await expect(page.getByRole('button', { name: 'Edit', exact: true })).toHaveCount(0);
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Accept|Authorize|Fabricate|Power on/i })).toHaveCount(0);

  await newest.getByRole('button', { name: 'Stop previewing' }).click();
  await expect(page.getByText(/Read-only review/i)).toBeVisible();
});

test('autoroute says plainly when the server cannot route and never offers it on a schematic', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await expect(page.locator('kicanvas-embed:not([data-retired])')).toHaveCount(1);

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByTestId('edit-dock')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Autoroute the board' })).toHaveCount(0);

  // Editing stays on when the artifact changes; its drafts do not.
  await page.getByRole('button', { name: 'PCB', exact: true }).click();
  const dock = page.getByTestId('edit-dock');
  await expect(dock.getByText('Not available on this server')).toBeVisible({ timeout: 15000 });
  await expect(dock.getByText(/FREEROUTING_JAR/)).toBeVisible();
  await expect(dock.getByRole('button', { name: 'Autoroute the board' })).toBeDisabled();
});

test('switching between schematic, PCB and 3D raises no uncaught browser errors', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await expect(page.locator('kicanvas-embed:not([data-retired])')).toHaveCount(1);

  await page.getByRole('button', { name: 'PCB', exact: true }).click();
  await page.waitForTimeout(1500);
  await page.getByRole('button', { name: 'Schematic', exact: true }).click();
  await page.waitForTimeout(1500);
  await page.getByRole('button', { name: '3D', exact: true }).click();
  await expect(page.getByTestId('model3d').locator('canvas')).toBeVisible({ timeout: 30000 });
  await page.getByRole('button', { name: 'PCB', exact: true }).click();
  await page.waitForTimeout(1500);

  expect(errors, `uncaught browser errors: ${errors.join(' | ')}`).toEqual([]);
});

test('only a verified operator can decide a proposal, and rejecting changes no revision', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.addInitScript(() => { localStorage.setItem('hs-review-author', 'Alice'); sessionStorage.removeItem('hs-operator-token'); });
  await page.goto(EVIDENCE);
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /^Proposals/ }).click();

  // Make sure there is a pending proposal to decide.
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.waitForFunction(() => Boolean(document.querySelector('kicanvas-embed:not([data-retired])')?.shadowRoot?.querySelector('kc-schematic-app')?.viewer?.canvas));
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });
  // The turn the other way must work on a schematic too, which only accepts 0, 90, 180 and 270.
  const reason = `Counter-turn U1 ${Date.now()}`;
  await page.getByRole('button', { name: 'Rotate 90 degrees counter-clockwise' }).click();
  await expect(page.getByTestId('edit-dock')).toContainText('Rotate U1 −90°');
  await page.getByLabel('Reason for the proposal').fill(reason);
  await page.getByRole('button', { name: /^Propose 1 change/ }).click();
  await expect(page.getByTestId('edit-dock').getByRole('alert')).toHaveCount(0);

  const card = page.getByTestId('proposal-card').filter({ hasText: reason });
  await expect(card.getByText('Not applied')).toBeVisible({ timeout: 15000 });

  // Without a token there is nothing to click that would decide it.
  await expect(card.getByText('Deciding needs an operator token')).toBeVisible();
  await expect(page.getByRole('button', { name: /^Accept|^Reject/ })).toHaveCount(0);

  await card.getByText('Deciding needs an operator token').click();
  await card.getByLabel('Operator token').fill('demo-operator-token');
  await expect(card.getByRole('button', { name: 'Accept as a new revision' })).toBeVisible();

  // Accepting asks first, and says what it does and does not do.
  await card.getByRole('button', { name: 'Accept as a new revision' }).click();
  await expect(card.getByText(/Make revision 7 from Alice's proposal \(rotate U1\)/)).toBeVisible();
  await expect(card.getByText(/does not verify the design or open fabrication/)).toBeVisible();
  await card.getByRole('button', { name: 'Cancel' }).click();

  await card.getByLabel('Reason for the decision').fill('Not now');
  await card.getByRole('button', { name: 'Reject', exact: true }).click();
  await expect(card.getByText(/Reject Alice's proposal \(rotate U1\)\. It stays on record/)).toBeVisible();
  await card.getByRole('button', { name: 'Reject proposal' }).click();
  await expect(card.getByText('Rejected', { exact: true }).first()).toBeVisible({ timeout: 10000 });
  await expect(card.getByText('demo-operator')).toBeVisible();
  await expect(card.getByText(/Not now/)).toBeVisible();
  await expect(card.getByRole('button', { name: /Accept|Reject|Make revision/ })).toHaveCount(0);
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();
});

test('switching artifacts rapidly while they are still loading raises no uncaught browser errors', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await expect(page.locator('kicanvas-embed:not([data-retired])')).toHaveCount(1);

  // Faster than KiCanvas can finish loading either file.
  for (let round = 0; round < 6; round += 1) {
    await page.getByRole('button', { name: 'PCB', exact: true }).click();
    await page.waitForTimeout(60);
    await page.getByRole('button', { name: 'Schematic', exact: true }).click();
    await page.waitForTimeout(60);
  }

  // One live viewer remains, nothing retired is left behind, and the file on screen is the one that was asked for.
  await expect(page.locator('kicanvas-embed:not([data-retired])')).toHaveCount(1, { timeout: 15000 });
  await expect(page.locator('kicanvas-embed[data-retired]')).toHaveCount(0, { timeout: 15000 });
  await page.waitForTimeout(500);
  expect(errors, `uncaught browser errors: ${errors.join(' | ')}`).toEqual([]);
});
