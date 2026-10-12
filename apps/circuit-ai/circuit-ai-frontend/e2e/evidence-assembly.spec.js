const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const EVIDENCE = `${APP_URL}/engineering/evidence?project=outsider-fixture`;

// Decode a screenshot inside the page and compare it with another, so "the board changed" is measured from what is drawn.
async function pixels(page, locator) {
  const png = await locator.screenshot();
  return png.toString('base64');
}
async function compare(page, a, b) {
  return page.evaluate(async ([first, second]) => {
    const load = async (base64) => {
      const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
      const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/png' }));
      const canvas = document.createElement('canvas');
      canvas.width = bitmap.width; canvas.height = bitmap.height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(bitmap, 0, 0);
      return ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    };
    const [one, two] = [await load(first), await load(second)];
    let differing = 0; let lit = 0;
    for (let i = 0; i < one.length; i += 4) {
      if (Math.abs(one[i] - two[i]) + Math.abs(one[i + 1] - two[i + 1]) + Math.abs(one[i + 2] - two[i + 2]) > 40) differing += 1;
      if (Math.max(two[i], two[i + 1], two[i + 2]) > 70) lit += 1;
    }
    return { differing, lit, total: one.length / 4 };
  }, [a, b]);
}

async function open(page) {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await page.getByTestId('assemble-tab').click();
  const viewer = page.getByTestId('assembly-viewer');
  await expect(viewer).toHaveAttribute('data-state', 'ready', { timeout: 30000 });
  await expect(viewer.locator('canvas')).toBeVisible({ timeout: 30000 });
  await settle(viewer);
  return viewer;
}
async function settle(viewer) {
  await expect(viewer).toHaveAttribute('data-flying', '0', { timeout: 20000 });
  await viewer.page().waitForTimeout(250);
}

test('the build plays as an animation: parts arrive on the board in order and every one ends up placed', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const viewer = await open(page);
  const stage = viewer.locator('canvas');

  await expect(page.getByTestId('assembly-counter')).toHaveText(/Step 1 of 12/);
  await expect(page.getByTestId('assembly-title')).toContainText('resistors');
  await expect(viewer).toHaveAttribute('data-placed', '5');   // R2, R3, R5, R6, R7: R1 and R4 are marked do-not-populate
  await expect(page.getByTestId('assembly-label')).toHaveCount(5);
  // The two parts the design leaves off are said to be left off, and are never part of a step.
  await expect(page.getByTestId('assembly-not-fitted')).toContainText('R1, R4');
  await expect(page.getByTestId('assembly-instruction')).not.toContainText('R1');
  await expect(page.getByTestId('assembly-prev')).toBeDisabled();

  const first = await pixels(page, stage);
  expect((await compare(page, first, first)).lit / (await compare(page, first, first)).total).toBeGreaterThan(0.03); // the board is drawn

  // Going forward animates: while parts are arriving the scene reports them as moving, and later nothing is.
  await page.getByTestId('assembly-next').click();
  await expect.poll(async () => Number(await viewer.getAttribute('data-flying')), { timeout: 4000 }).toBeGreaterThan(0);
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-placed', '8');   // the five resistors and C3-C5
  await expect(page.getByTestId('assembly-instruction')).toContainText('C3');

  // Parts really appear on screen.
  const second = await pixels(page, stage);
  expect((await compare(page, first, second)).differing).toBeGreaterThan(150);

  // The last step has every part in place and the checks to try before power.
  await page.getByTestId('assembly-slider').focus();
  await page.keyboard.press('End');
  await expect(page.getByTestId('assembly-counter')).toHaveText(/Step 12 of 12/);
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-placed', '38');
  await expect(page.getByTestId('assembly-checks')).toContainText('meter between');
  await expect(page.getByTestId('assembly-checks')).toContainText('NOT connected');
  await expect(page.getByTestId('assembly-next')).toBeDisabled();
  await expect(page.getByTestId('assembly-label')).toHaveCount(0);

  expect(errors).toEqual([]);
});

test('a big group is named in the panel instead of crowding the board with labels, and nothing authoritative is claimed', async ({ page }) => {
  const viewer = await open(page);
  // Step 8 is the 18 test points.
  await page.getByTestId('assembly-slider').focus();
  for (let i = 0; i < 7; i += 1) await page.keyboard.press('ArrowRight');
  await expect(page.getByTestId('assembly-counter')).toHaveText(/Step 8 of 12/);
  await settle(viewer);
  await expect(page.getByTestId('assembly-title')).toContainText('18 test points');
  await expect(page.getByTestId('assembly-label')).toHaveCount(0);
  const panel = page.getByTestId('assembly-panel');
  await expect(panel).toContainText('Nothing here approves building, powering or releasing the board.');
  await expect(viewer).toContainText('Stand-in shapes');
});

test('play runs the steps by itself and pauses, and the arrow keys and the slider move through it', async ({ page }) => {
  const viewer = await open(page);
  await page.getByTestId('assembly-play').click();
  await expect(page.getByTestId('assembly-play')).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(async () => Number(await viewer.getAttribute('data-step')), { timeout: 15000 }).toBeGreaterThanOrEqual(2);
  await page.getByTestId('assembly-play').click();
  await expect(page.getByTestId('assembly-play')).toHaveAttribute('aria-pressed', 'false');
  const stopped = await viewer.getAttribute('data-step');
  await page.waitForTimeout(2500);
  expect(await viewer.getAttribute('data-step')).toBe(stopped);

  await viewer.focus();
  await page.keyboard.press('ArrowLeft');
  await expect(viewer).toHaveAttribute('data-step', String(Number(stopped) - 1));
  await page.keyboard.press('ArrowRight');
  await expect(viewer).toHaveAttribute('data-step', stopped);
  // Starting again returns to the first step with only its parts placed.
  await page.getByRole('button', { name: 'Start again' }).click();
  await expect(viewer).toHaveAttribute('data-step', '0');
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-placed', '5');
});

test('stepping backwards takes parts off the board again and leaving the tab leaves no errors behind', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const viewer = await open(page);
  await page.getByTestId('assembly-slider').focus();
  for (let i = 0; i < 5; i += 1) await page.keyboard.press('ArrowRight');
  await settle(viewer);
  const far = await viewer.getAttribute('data-placed');
  expect(Number(far)).toBeGreaterThan(10);
  for (let i = 0; i < 5; i += 1) await page.keyboard.press('ArrowLeft');
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-placed', '5');

  await page.getByRole('button', { name: 'PCB', exact: true }).click();
  await expect(page.getByTestId('assembly-viewer')).toHaveCount(0);
  await page.getByTestId('assemble-tab').click();
  await expect(page.getByTestId('assembly-viewer')).toHaveAttribute('data-state', 'ready', { timeout: 30000 });
  expect(errors).toEqual([]);
});


test('leaving the tab while the board is still loading releases the graphics context instead of leaking it', async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    window.__contexts = [];
    HTMLCanvasElement.prototype.getContext = function (kind, ...rest) {
      const context = original.call(this, kind, ...rest);
      // Only contexts made while the build view is on screen: the PCB tab's own viewer legitimately keeps one of its own.
      if (context && String(kind).startsWith('webgl') && document.querySelector('[data-testid="assembly-viewer"]')) window.__contexts.push(context);
      return context;
    };
  });
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  await page.route('**/assembly-plan/board.glb', async (route) => {
    await held;
    await route.continue();
  });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await page.getByTestId('assemble-tab').click();
  await expect.poll(() => page.evaluate(() => window.__contexts.length)).toBeGreaterThan(0);   // the scene started and is waiting for the board
  await page.getByRole('button', { name: 'PCB', exact: true }).click();                          // leave before it arrives
  await expect(page.getByTestId('assembly-viewer')).toHaveCount(0);
  release();
  await page.waitForTimeout(1200);
  const lost = await page.evaluate(() => window.__contexts.map((context) => context.isContextLost()));
  expect(lost.length).toBeGreaterThan(0);
  expect(lost.every(Boolean)).toBe(true);
  expect(errors).toEqual([]);
});

test('a board where every part is left off says so in the view instead of claiming there is nothing to show', async ({ page }) => {
  const plan = {
    authority: 'This is a view of the retained board file. Nothing here approves building, powering or releasing the board.',
    not_fitted: ['R1', 'R2'],
    board: { thickness_mm: 1.6, size_mm: [20, 10], outline: { kind: 'rectangle', bbox: { x0: 0, y0: 0, x1: 20, y1: 10 } } },
    parts: [],
    warnings: [],
    steps: [{
      step_id: 'step-01', order: 1, title: 'Nothing to fit on this board',
      instruction: 'Every part on this board is marked do-not-populate, so there is nothing to place. Not fitted on this board (marked do-not-populate): R1, R2.',
      kind: 'verify', side: 'front', turn_board_over: false, refs: [], part_ids: [], checks: [],
    }],
  };
  await page.route('**/assembly-plan', (route) => route.fulfill({ json: { ok: true, revision: 6, available: true, plan } }));
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await page.getByTestId('assemble-tab').click();
  const viewer = page.getByTestId('assembly-viewer');
  await expect(viewer).toHaveAttribute('data-state', 'ready', { timeout: 30000 });
  await expect(page.getByTestId('assembly-title')).toHaveText('Nothing to fit on this board');
  await expect(page.getByTestId('assembly-not-fitted')).toContainText('R1, R2');
  await expect(page.getByTestId('assembly-counter')).toHaveText(/Step 1 of 1/);
  await expect(page.getByTestId('assembly-next')).toBeDisabled();
  await expect(viewer).toHaveAttribute('data-placed', '0');
  expect(errors).toEqual([]);
});
