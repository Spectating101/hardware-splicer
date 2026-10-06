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

test('a draft is previewed live with the changes marked, keeps the view, reports a refused edit and saves nothing', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.addInitScript(() => localStorage.setItem('hs-review-author', 'Alice'));
  await page.goto(EVIDENCE);
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible();
  const proposalsBefore = async () => (await (await page.request.get(`${APP_URL}/api/proxy/engineering/projects/outsider-fixture/candidates`)).json()).candidates.length;
  const before = await proposalsBefore();

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.waitForFunction(() => Boolean(document.querySelector('kicanvas-embed:not([data-retired])')?.shadowRoot?.querySelector('kc-schematic-app')?.viewer?.canvas));
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });

  // A distinctive view, so keeping it is observable.
  const camera = () => page.evaluate(() => {
    const c = document.querySelector('kicanvas-embed:not([data-retired])').shadowRoot.querySelector('kc-schematic-app').viewer.viewport.camera;
    return { x: c.center.x, y: c.center.y, zoom: c.zoom };
  });
  await page.evaluate(() => {
    const viewer = document.querySelector('kicanvas-embed:not([data-retired])').shadowRoot.querySelector('kc-schematic-app').viewer;
    viewer.viewport.camera.zoom = viewer.viewport.camera.zoom * 2.2;
    viewer.draw();
  });
  const view = await camera();

  await page.getByRole('button', { name: 'Rotate 90 degrees clockwise' }).click();
  await expect(page.getByText('Draft preview · not saved')).toBeVisible({ timeout: 10000 });
  await expect(page.getByTestId('diff-highlight').first()).toBeVisible({ timeout: 10000 });
  await expect(page.getByTestId('edit-dock')).toContainText('Nothing is saved until you propose');

  // The reload put the person's zoom and pan back.
  await expect.poll(async () => {
    const now = await camera();
    return Math.abs(now.zoom - view.zoom) / view.zoom < 0.02 && Math.abs(now.x - view.x) < 1 && Math.abs(now.y - view.y) < 1;
  }, { timeout: 10000 }).toBe(true);

  // The part is still chosen after the reload, so editing can continue.
  await expect(page.getByTestId('edit-dock')).toContainText('U1');
  await page.getByLabel('X position in millimetres').fill('999999999');
  await page.getByLabel('Y position in millimetres').fill('10');
  await page.getByRole('button', { name: 'Move', exact: true }).click();
  await expect(page.getByTestId('edit-dock').getByRole('alert')).toContainText("can't be applied", { timeout: 10000 });
  await expect(page.getByRole('button', { name: /^Propose 2 changes/ })).toBeDisabled();

  // Removing the offending change brings the preview back.
  await page.getByRole('button', { name: /^Remove: Move U1/ }).click();
  await expect(page.getByTestId('edit-dock').getByRole('alert')).toHaveCount(0);
  await expect(page.getByText('Draft preview · not saved')).toBeVisible({ timeout: 10000 });

  // Closing the dock discards the draft: the retained file is back, and nothing was ever created.
  await page.getByRole('button', { name: 'Close editing' }).click();
  await expect(page.getByText('Read-only review')).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('Draft preview · not saved')).toHaveCount(0);
  expect(await proposalsBefore()).toBe(before);
});

// A project with a second schematic offered under another path: the same content, which the revision does not retain as
// its editable schematic.
async function offerSecondSchematic(page, relative) {
  let firstSchematic = '';
  await page.route('**/api/proxy/hardware-splicer/build-files/list', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const first = (body.files || []).find((file) => file.kind === 'schematic');
    firstSchematic = first.relative;
    await route.fulfill({ response, json: { ...body, files: [...body.files, { ...first, name: relative.split('/').pop(), relative }] } });
  });
  await page.route('**/api/proxy/hardware-splicer/build-files/content', async (route) => {
    const request = route.request().postDataJSON();
    if (request.relative !== relative) { await route.continue(); return; }
    const original = await route.fetch({ postData: JSON.stringify({ ...request, relative: firstSchematic }) });
    await route.fulfill({ response: original });
  });
}

const viewerReady = (page) => page.waitForFunction(() => Boolean(document.querySelector('kicanvas-embed:not([data-retired])')?.shadowRoot?.querySelector('kc-schematic-app')?.viewer?.canvas));

test('a draft and a selection belong to one file: another schematic never shows or inherits them', async ({ page }) => {
  await offerSecondSchematic(page, 'sheets/sheet_two.kicad_sch');
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.addInitScript(() => localStorage.setItem('hs-review-author', 'Alice'));
  await page.goto(EVIDENCE);
  await expect(page.getByRole('button', { name: 'sheet_two', exact: true })).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('button', { name: 'spi_flash_adapter_v1', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await viewerReady(page);
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });
  await page.getByRole('button', { name: 'Rotate 90 degrees clockwise' }).click();
  await expect(page.getByText('Draft preview · not saved')).toBeVisible({ timeout: 10000 });

  // Another file of the same kind: the draft and the selection do not come along.
  await page.getByRole('button', { name: 'sheet_two', exact: true }).click();
  await expect(page.getByText('Draft preview · not saved')).toHaveCount(0, { timeout: 10000 });
  await expect(page.getByTestId('edit-dock')).toContainText('Select a part to change it');
  await expect(page.getByRole('button', { name: /^Propose/ })).toHaveCount(0);

  // Editing a file the revision does not retain as its schematic is refused in words, not drawn under the wrong name.
  await viewerReady(page);
  const second = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(second.x, second.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });
  await page.getByRole('button', { name: 'Rotate 90 degrees clockwise' }).click();
  await expect(page.getByTestId('edit-dock').getByRole('alert')).toContainText('keeps spi_flash_adapter_v1.kicad_sch as its editable schematic', { timeout: 10000 });
  await expect(page.getByText('Draft preview · not saved')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Propose 1 change/ })).toBeDisabled();
});

test('a selection made with no draft does not follow the person to another file with identical content', async ({ page }) => {
  await offerSecondSchematic(page, 'sheets/sheet_two.kicad_sch');
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await expect(page.getByRole('button', { name: 'sheet_two', exact: true })).toBeVisible({ timeout: 15000 });

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await viewerReady(page);
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });

  await page.getByRole('button', { name: 'sheet_two', exact: true }).click();
  // Long enough for the dock to read the new viewer more than once.
  await page.waitForTimeout(1500);
  await expect(page.getByTestId('edit-dock')).toContainText('Select a part to change it');
  await expect(page.getByTestId('edit-dock')).not.toContainText('U1');
});

test('files that share a name are told apart by their folder, and a draft is never drawn over the wrong one', async ({ page }) => {
  // The retained schematic is spi_flash_adapter_v1.kicad_sch; this is a different file that has the same name.
  await offerSecondSchematic(page, 'copy/spi_flash_adapter_v1.kicad_sch');
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.addInitScript(() => localStorage.setItem('hs-review-author', 'Alice'));
  await page.goto(EVIDENCE);
  const copyTab = page.getByRole('button', { name: 'copy/spi_flash_adapter_v1', exact: true });
  await expect(copyTab).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('button', { name: 'spi_flash_adapter_v1', exact: true })).toBeVisible();

  await copyTab.click();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await viewerReady(page);
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });
  await page.getByRole('button', { name: 'Rotate 90 degrees clockwise' }).click();

  await expect(page.getByTestId('edit-dock').getByRole('alert')).toContainText('not the file on screen', { timeout: 10000 });
  await expect(page.getByText('Draft preview · not saved')).toHaveCount(0);
});

test('moving to another file ends a search for a part, so it never selects something on the file the person went to', async ({ page }) => {
  await offerSecondSchematic(page, 'sheets/sheet_two.kicad_sch');
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await expect(page.getByRole('button', { name: 'sheet_two', exact: true })).toBeVisible({ timeout: 15000 });
  await page.getByRole('button', { name: 'PCB', exact: true }).click();
  await page.getByRole('button', { name: /^Parts/ }).click();

  // Ask for U2 (the schematic starts opening), then at once go to the other sheet.
  await page.getByTestId('parts-panel').getByRole('button', { name: 'U2', exact: true }).first().click();
  await page.getByRole('button', { name: 'sheet_two', exact: true }).click();
  await viewerReady(page);
  await page.waitForTimeout(3000);

  const selected = await page.evaluate(() => document.querySelector('kicanvas-embed:not([data-retired])')?.shadowRoot?.querySelector('kc-schematic-app')?.viewer?.selected?.context?.reference || null);
  expect(selected).toBeNull();
});

test('a proposal is drawn over the retained file it changed, found by its retained path and not its storage name', async ({ page }) => {
  await offerSecondSchematic(page, 'sheets/sheet_two.kicad_sch');
  // The proposal's own record: stored under a plain name in its folder, retained from sheets/sheet_two.kicad_sch.
  await page.route('**/api/proxy/engineering/projects/outsider-fixture/candidates', async (route) => {
    if (route.request().method() !== 'GET') { await route.continue(); return; }
    const response = await route.fetch();
    const body = await response.json();
    const candidates = (body.candidates || []).map((candidate) => ({
      ...candidate,
      files: { schematic: { relative: 'sheet_two.kicad_sch', retained_relative: 'sheets/sheet_two.kicad_sch', sha256: null } },
    }));
    await route.fulfill({ response, json: { ...body, candidates } });
  });
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.addInitScript(() => localStorage.setItem('hs-review-author', 'Alice'));
  await page.goto(EVIDENCE);
  await expect(page.getByRole('button', { name: 'sheet_two', exact: true })).toBeVisible({ timeout: 15000 });

  const reason = `Second sheet ${Date.now()}`;
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await viewerReady(page);
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });
  await page.getByRole('button', { name: 'Rotate 90 degrees clockwise' }).click();
  await page.getByLabel('Reason for the proposal').fill(reason);
  await page.getByRole('button', { name: /^Propose 1 change/ }).click();

  const card = page.getByTestId('proposal-card').filter({ hasText: reason });
  await expect(card).toBeVisible({ timeout: 15000 });
  await card.getByRole('button', { name: 'Preview with changes marked' }).click();

  // It opened sheet_two, the file named by the retained path, not the first schematic.
  await expect(page.getByText('sheets/sheet_two.kicad_sch', { exact: true })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('Proposal preview · not applied')).toBeVisible();
});

test('a proposal recorded without the path of its file is not drawn over a file by guesswork', async ({ page }) => {
  await page.route('**/api/proxy/engineering/projects/outsider-fixture/candidates', async (route) => {
    if (route.request().method() !== 'GET') { await route.continue(); return; }
    const response = await route.fetch();
    const body = await response.json();
    // An older record: it names a stored file but not where that file was retained from.
    const candidates = (body.candidates || []).map((candidate) => ({ ...candidate, files: { [candidate.kind]: { relative: 'spi_flash_adapter_v1.kicad_sch', sha256: null } } }));
    await route.fulfill({ response, json: { ...body, candidates } });
  });
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.addInitScript(() => localStorage.setItem('hs-review-author', 'Alice'));
  await page.goto(EVIDENCE);
  await expect(page.locator('kicanvas-embed:not([data-retired])')).toHaveCount(1);

  const reason = `Older record ${Date.now()}`;
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await viewerReady(page);
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });
  await page.getByRole('button', { name: 'Rotate 90 degrees clockwise' }).click();
  await page.getByLabel('Reason for the proposal').fill(reason);
  await page.getByRole('button', { name: /^Propose 1 change/ }).click();

  const card = page.getByTestId('proposal-card').filter({ hasText: reason });
  await expect(card).toBeVisible({ timeout: 15000 });
  await card.getByRole('button', { name: 'Preview with changes marked' }).click();

  await expect(page.getByRole('alert').filter({ hasText: 'without the path of the file it changed' })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('Proposal preview · not applied')).toHaveCount(0);
});

test('a file that is slow or fails to load never shows, or lends its selection to, the previous file', async ({ page }) => {
  await offerSecondSchematic(page, 'sheets/sheet_two.kicad_sch');
  let mode = 'slow';
  await page.route('**/api/proxy/hardware-splicer/build-files/content', async (route) => {
    const request = route.request().postDataJSON();
    if (request.relative !== 'sheets/sheet_two.kicad_sch') { await route.fallback(); return; }
    if (mode === 'fail') { await route.fulfill({ status: 500, json: { ok: false } }); return; }
    await new Promise((resolve) => setTimeout(resolve, 2500));
    await route.fallback();
  });
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await expect(page.getByRole('button', { name: 'sheet_two', exact: true })).toBeVisible({ timeout: 15000 });

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await viewerReady(page);
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });

  // While the second file is still loading, the first file's viewer must not stand in for it.
  await page.getByRole('button', { name: 'sheet_two', exact: true }).click();
  await page.waitForTimeout(900);
  await expect(page.getByTestId('edit-dock')).toContainText('Select a part to change it');
  await expect(page.locator('kicanvas-embed:not([data-retired])')).toHaveCount(0);
  await viewerReady(page);
  await page.waitForTimeout(800);
  await expect(page.getByTestId('edit-dock')).toContainText('Select a part to change it');

  // A file that cannot be loaded leaves no viewer at all, and says so.
  mode = 'fail';
  await page.getByRole('button', { name: 'spi_flash_adapter_v1', exact: true }).click();
  await viewerReady(page);
  await page.getByRole('button', { name: 'sheet_two', exact: true }).click();
  await expect(page.getByText('Artifact content is unavailable.')).toBeVisible({ timeout: 10000 });
  await expect(page.locator('kicanvas-embed:not([data-retired])')).toHaveCount(0);

  // Going back to the file that did load puts its viewer back, even though its text is identical to what was shown before.
  await page.getByRole('button', { name: 'spi_flash_adapter_v1', exact: true }).click();
  await expect(page.locator('kicanvas-embed:not([data-retired])')).toHaveCount(1, { timeout: 10000 });
  await viewerReady(page);
});

test('switching to another project with a file of the same path ends editing and discards the draft', async ({ page }) => {
  // A second project that is the same fixture under another id, so its files have identical paths.
  await page.route('**/api/proxy/engineering/projects', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const copy = { ...body.projects[0], project_id: 'outsider-fixture-copy', name: 'Copy of the fixture', project_name: 'Copy of the fixture' };
    await route.fulfill({ response, json: { ...body, projects: [...body.projects, copy] } });
  });
  await page.route('**/api/proxy/engineering/projects/outsider-fixture-copy/**', async (route) => {
    await route.continue({ url: route.request().url().replace('outsider-fixture-copy', 'outsider-fixture') });
  });
  await page.route('**/api/proxy/engineering/projects/outsider-fixture-copy', async (route) => {
    await route.continue({ url: route.request().url().replace('outsider-fixture-copy', 'outsider-fixture') });
  });
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await expect(page.getByRole('combobox', { name: 'Project' })).toBeVisible();

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await viewerReady(page);
  const point = await symbolScreenPoint(page, 'U1');
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('edit-dock')).toContainText('U1', { timeout: 8000 });
  await page.getByRole('button', { name: 'Rotate 90 degrees clockwise' }).click();
  await expect(page.getByText('Draft preview · not saved')).toBeVisible({ timeout: 10000 });

  await page.getByRole('combobox', { name: 'Project' }).selectOption('outsider-fixture-copy');
  await expect(page.getByRole('combobox', { name: 'Project' })).toHaveValue('outsider-fixture-copy');
  // The page really loaded the other project: its requests went to the copy's id.
  await expect(page.getByText('Rev 6', { exact: true })).toBeVisible({ timeout: 10000 });

  // Nothing from the first project's session carries over.
  await expect(page.getByText('Draft preview · not saved')).toHaveCount(0, { timeout: 10000 });
  await expect(page.getByTestId('edit-dock')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Propose/ })).toHaveCount(0);
});

test('copper fills are faint by default so tracks and pads stay readable, and can be shown in full', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await expect(page.getByRole('button', { name: /^Copper fills/ })).toHaveCount(0);
  await page.getByRole('button', { name: 'PCB', exact: true }).click();
  const toggle = page.getByRole('button', { name: 'Copper fills: faint' });
  await expect(toggle).toBeVisible();

  const zoneOpacity = () => page.evaluate(() => {
    const viewer = document.querySelector('kicanvas-embed:not([data-retired])')?.shadowRoot?.querySelector('kc-board-app')?.viewer;
    const zones = Array.from(viewer?.layers?.in_display_order?.() || []).filter((layer) => /Zones$/.test(layer.name));
    return zones.length ? zones.map((layer) => layer.opacity) : null;
  });
  await expect.poll(zoneOpacity, { timeout: 15000 }).toEqual(expect.arrayContaining([0.22]));

  await toggle.click();
  await expect(page.getByRole('button', { name: 'Copper fills: full' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(zoneOpacity, { timeout: 5000 }).toEqual(expect.arrayContaining([1]));

  // The choice survives a reload of the same board (a draft or a previewed proposal replaces the viewer).
  await page.getByRole('button', { name: 'Schematic', exact: true }).click();
  await expect(page.getByRole('button', { name: /^Copper fills/ })).toHaveCount(0);
});

test('a part in the Parts tab can be found on the drawing, from any tab', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await page.getByRole('button', { name: 'PCB', exact: true }).click();
  await expect(page.getByRole('button', { name: /^Copper fills/ })).toBeVisible();

  await page.getByRole('button', { name: /^Parts/ }).click();
  await page.getByTestId('parts-panel').getByRole('button', { name: 'U2', exact: true }).first().click();

  // It switched to the schematic and selected the part there.
  await expect(page.getByRole('button', { name: /^Copper fills/ })).toHaveCount(0, { timeout: 10000 });
  await expect.poll(() => page.evaluate(() => {
    const viewer = document.querySelector('kicanvas-embed:not([data-retired])')?.shadowRoot?.querySelector('kc-schematic-app')?.viewer;
    return viewer?.selected?.context?.reference || null;
  }), { timeout: 15000 }).toBe('U2');
});
