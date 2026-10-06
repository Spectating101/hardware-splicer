const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const EVIDENCE = `${APP_URL}/engineering/evidence?project=outsider-fixture`;

// Screen position of a placed schematic symbol, from the viewer's own camera, so the click lands on the part
// regardless of the surrounding layout.
async function symbolScreenPoint(page, reference) {
  return page.evaluate((ref) => {
    const viewer = document.querySelector('kicanvas-embed').shadowRoot.querySelector('kc-schematic-app').viewer;
    const symbols = Array.from(viewer.schematic.symbols.values ? viewer.schematic.symbols.values() : viewer.schematic.symbols);
    const symbol = symbols.find((item) => item.reference === ref);
    const point = viewer.viewport.camera.world_to_screen({ x: symbol.at.position.x, y: symbol.at.position.y });
    const rect = viewer.canvas.getBoundingClientRect();
    return { x: point.x + rect.left, y: point.y + rect.top };
  }, reference);
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
  await expect(page.locator('kicanvas-embed')).toHaveCount(1);
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
  await expect(page.locator('kicanvas-embed')).toHaveCount(1);
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByTestId('edit-dock')).toContainText('Select a part');
  await expect(page.getByText('Drafting a proposal')).toBeVisible();

  await page.waitForFunction(() => {
    const app = document.querySelector('kicanvas-embed')?.shadowRoot?.querySelector('kc-schematic-app');
    return Boolean(app && app.viewer && app.viewer.schematic && app.viewer.canvas);
  });
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });

  await page.getByRole('button', { name: 'Rotate 90 degrees clockwise' }).click();
  await page.getByRole('button', { name: /^Propose 1 change/ }).click();

  const panel = page.getByTestId('proposals-panel');
  // Newest first; earlier runs against a long-lived fixture backend may have left older proposals.
  const newest = panel.locator('li').first();
  await expect(newest.getByText('Not applied')).toBeVisible({ timeout: 15000 });
  await expect(newest.getByText(/rotate U1/)).toBeVisible();
  await expect(newest.getByText(/does not accept or reject anything/)).toBeVisible();

  await newest.getByRole('button', { name: 'Preview in viewer' }).click();
  await expect(page.getByText(/Proposal preview/i)).toBeVisible();
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
  await expect(page.locator('kicanvas-embed')).toHaveCount(1);

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
  await expect(page.locator('kicanvas-embed')).toHaveCount(1);

  await page.getByRole('button', { name: 'PCB', exact: true }).click();
  await page.waitForTimeout(1500);
  await page.getByRole('button', { name: 'Schematic', exact: true }).click();
  await page.waitForTimeout(1500);
  await page.getByRole('button', { name: '3D', exact: true }).click();
  await expect(page.getByTestId('model3d').locator('canvas')).toBeVisible({ timeout: 30000 });
  await page.getByRole('button', { name: 'PCB', exact: true }).click();
  await page.waitForTimeout(1500);

  expect(errors).toEqual([]);
});
