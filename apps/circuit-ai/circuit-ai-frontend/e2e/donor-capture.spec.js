const { test, expect } = require('@playwright/test');
const fs = require('node:fs');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const DONOR = `${APP_URL}/engineering/donor`;
// A 1 x 1 PNG, enough to test the photo underlay.
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');

async function open(page, { fresh = true } = {}) {
  await page.setViewportSize({ width: 1500, height: 1000 });
  if (fresh) await page.addInitScript(() => { try { if (!sessionStorage.getItem('__seeded')) { localStorage.clear(); sessionStorage.setItem('__seeded', '1'); } } catch { /* ignore */ } });
  await page.goto(DONOR);
  await expect(page.getByTestId('donor-kind').locator('option')).not.toHaveCount(0, { timeout: 20000 });
}
async function viewerReady(page) {
  const viewer = page.getByTestId('assembly-viewer');
  await expect(viewer).toHaveAttribute('data-state', 'ready', { timeout: 30000 });
  await expect(viewer.locator('canvas')).toBeVisible({ timeout: 30000 });
  await expect(viewer).toHaveAttribute('data-flying', '0', { timeout: 20000 });
  return viewer;
}
async function centreOf(locator) {
  const box = await locator.boundingBox();
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

test('describe one chip, read its marking, and watch the advice change when the marking does', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await open(page);
  await expect(page.getByTestId('donor-parts-list')).toContainText('None yet');

  await page.getByTestId('donor-add-centre').click();
  const chip = page.getByTestId('donor-part-U1');
  await expect(chip).toBeVisible();
  await expect(chip).toHaveAttribute('data-selected', '1');
  await page.getByTestId('donor-marking').fill('NE555');
  await page.getByTestId('donor-plan').click();
  const viewer = await viewerReady(page);
  await expect(page.getByTestId('assembly-counter')).toHaveText(/Step 1 of 3/);
  await expect(viewer).toHaveAttribute('data-placed', '1');
  await page.getByTestId('assembly-next').click();
  await expect(page.getByTestId('assembly-verdict')).toHaveAttribute('data-verdict', 'keep');
  // What you typed is called what you read, never what a file says.
  await expect(page.getByTestId('assembly-instruction')).toContainText('you read its marking as "NE555"');
  await expect(page.getByTestId('assembly-instruction')).not.toContainText('board file');
  await expect(page.getByTestId('salvage-limits')).toContainText('what you typed or placed');
  await expect(page.getByTestId('salvage-limits')).toContainText('house code');
  // A board described by a person is never described as read from a file, and its sizes are called typical.
  await expect(page.getByTestId('assembly-panel')).toContainText('from what you described');
  await expect(page.getByTestId('assembly-panel')).not.toContainText('read from its file');
  await expect(viewer).toContainText('Sizes are typical for each package unless you typed them');
  await expect(viewer).not.toContainText('pad positions');
  await expect(page.getByTestId('donor-parts-list')).toContainText('Worth taking');

  // Change the marking: the plan is out of date until it is made again, and then the verdict follows.
  await page.getByTestId('donor-marking').fill('');
  await expect(page.getByTestId('donor-stale')).toBeVisible();
  await expect(page.getByTestId('donor-parts-list')).not.toContainText('Worth taking');
  await page.getByTestId('donor-plan').click();
  await expect(page.getByTestId('donor-stale')).toHaveCount(0);
  await viewerReady(page);
  await page.getByTestId('assembly-slider').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByTestId('assembly-verdict')).toHaveAttribute('data-verdict', 'identify');
  await expect(page.getByTestId('assembly-instruction')).toContainText('read it off the chip');
  expect(errors).toEqual([]);
});

test('click the board to place a part, drag it, and nudge and delete it from the keyboard', async ({ page }) => {
  await open(page);
  const canvas = page.getByTestId('donor-canvas');
  const box = await canvas.boundingBox();
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5);
  const part = page.getByTestId('donor-part-U1');
  await expect(part).toBeVisible();
  const before = await centreOf(part);

  // Drag it a good way to the right and down.
  await page.mouse.move(before.x, before.y);
  await page.mouse.down();
  await page.mouse.move(before.x + 80, before.y + 40, { steps: 8 });
  await page.mouse.up();
  const dragged = await centreOf(part);
  expect(dragged.x - before.x).toBeGreaterThan(50);
  expect(dragged.y - before.y).toBeGreaterThan(20);
  await expect(page.getByTestId('donor-parts-list').locator('li')).toHaveCount(1);          // the drag did not also place a part

  // Keyboard: arrows move it, and Delete removes it.
  await page.locator('[aria-label^="Board, seen from above"]').focus();
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowLeft');
  const nudged = await centreOf(part);
  expect(nudged.x).toBeLessThan(dragged.x);
  await page.keyboard.press('Delete');
  await expect(part).toHaveCount(0);
  await expect(page.getByTestId('donor-parts-list')).toContainText('None yet');
});

test('the example shows hazards named, what is left alone, and the 3D take-apart of a board nobody has a file for', async ({ page }) => {
  await open(page);
  await page.getByTestId('donor-example').click();
  await expect(page.getByTestId('donor-notice')).toContainText('made up');
  await expect(page.getByTestId('donor-parts-list').locator('li')).toHaveCount(9);
  await page.getByTestId('donor-plan').click();
  const viewer = await viewerReady(page);
  await expect(page.getByTestId('salvage-summary')).toContainText('worth taking');
  await expect(page.getByTestId('assembly-counter')).toHaveText(/Step 1 of \d+/);
  await page.getByTestId('assembly-slider').focus();
  await page.keyboard.press('End');
  await expect(viewer).toHaveAttribute('data-removed', /[1-9]/);
  // The fuse is a mains-class part: it is never "worth taking", and the reason is on screen at some step.
  const titles = [];
  for (let i = 0; i < 12; i += 1) {
    await page.keyboard.press('Home');
    for (let s = 0; s < i; s += 1) await page.keyboard.press('ArrowRight');
    if ((await page.getByTestId('assembly-title').count()) === 0) break;
    titles.push(await page.getByTestId('assembly-title').innerText());
    if (/Sort, label/.test(titles[titles.length - 1])) break;
  }
  expect(titles.some((t) => /Make the board safe/.test(t))).toBe(true);
  await expect(page.getByTestId('donor-parts-list')).toContainText('Leave it');            // the 0603 resistor and the cell are left alone
});

test('a description the planner cannot use is explained in plain words, and fixing it works', async ({ page }) => {
  await open(page);
  await page.getByTestId('donor-add-centre').click();
  await page.getByTestId('donor-ref').fill('U 1!');
  await page.getByTestId('donor-plan').click();
  await expect(page.getByTestId('donor-error')).toContainText('letters, digits and underscores');
  await page.getByTestId('donor-ref').fill('U1');
  await page.getByTestId('donor-plan').click();
  await viewerReady(page);
  await expect(page.getByTestId('donor-error')).toHaveCount(0);
});

test('your work is kept in this browser, and Start again clears it', async ({ page }) => {
  await open(page);
  await page.getByTestId('donor-name').fill('Router from the skip');
  await page.getByTestId('donor-add-centre').click();
  await page.getByTestId('donor-marking').fill('AR9331');
  await page.waitForTimeout(700);                                                         // it is saved shortly after each change
  await page.reload();
  await expect(page.getByTestId('donor-name')).toHaveValue('Router from the skip');
  await expect(page.getByTestId('donor-part-U1')).toBeVisible();
  await page.getByTestId('donor-part-U1').click({ force: true });
  await expect(page.getByTestId('donor-marking')).toHaveValue('AR9331');
  await page.getByTestId('donor-reset').click();
  await expect(page.getByTestId('donor-part-U1')).toHaveCount(0);
  await expect(page.getByTestId('donor-name')).toHaveValue('My donor board');
});

test('save writes a file you can open again, and a file that is not a board is refused politely', async ({ page }, testInfo) => {
  await open(page);
  await page.getByTestId('donor-example').click();
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Save' }).click()]);
  const saved = testInfo.outputPath('board.json');
  await download.saveAs(saved);
  const data = JSON.parse(fs.readFileSync(saved, 'utf8'));
  expect(data.schema_version).toBe('hardware_splicer.donor_capture.v1');
  expect(data.parts).toHaveLength(9);
  expect(data.parts[0].key).toBeUndefined();                                             // nothing internal leaks into the file
  await page.getByTestId('donor-reset').click();
  await page.locator('input[type=file][accept*="json"]').setInputFiles(saved);
  await expect(page.getByTestId('donor-notice')).toContainText('Loaded 9 parts');
  await expect(page.getByTestId('donor-parts-list').locator('li')).toHaveCount(9);
  const junk = testInfo.outputPath('junk.json');
  fs.writeFileSync(junk, '{"hello": "world"}');
  await page.locator('input[type=file][accept*="json"]').setInputFiles(junk);
  await expect(page.getByTestId('donor-notice')).toContainText('not a board description');
  await expect(page.getByTestId('donor-parts-list').locator('li')).toHaveCount(9);        // the board you had is untouched
});

test('a photo goes under the board in the browser only, and the board takes its shape', async ({ page }) => {
  const uploads = [];
  page.on('request', (request) => { if (request.method() === 'POST') uploads.push(request.url()); });
  await open(page);
  await page.getByTestId('donor-width').fill('80');
  await page.getByTestId('donor-photo').setInputFiles({ name: 'board.png', mimeType: 'image/png', buffer: PNG });
  await expect(page.getByTestId('donor-canvas').locator('image')).toHaveCount(1);
  await expect(page.getByTestId('donor-length')).toHaveValue('80');                       // a 1 x 1 photo makes a square board
  await expect(page.getByText('stays in this browser tab')).toBeVisible();
  expect(uploads).toEqual([]);                                                            // nothing was sent anywhere
});

test('a phone-sized screen has no sideways scrolling', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(DONOR);
  await expect(page.getByTestId('donor-canvas')).toBeVisible({ timeout: 20000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
});

// --- review findings (Grok), each reproduced before it was fixed -------------------------------------------------------------

test('a plan still on its way when you start again does not appear on the new board', async ({ page }) => {
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  await page.route('**/donors/salvage-plan', async (route) => { await held; await route.continue(); });
  await open(page);
  await page.getByTestId('donor-example').click();
  await page.getByTestId('donor-plan').click();
  await expect(page.getByTestId('donor-plan')).toBeDisabled();                        // asked, not answered
  await page.getByTestId('donor-reset').click();
  await expect(page.getByTestId('donor-plan')).toBeEnabled();                         // starting again frees the button
  release();
  await page.waitForTimeout(1200);
  await expect(page.getByTestId('assembly-viewer')).toHaveCount(0);                    // the example's plan never reached the empty board
  await expect(page.getByTestId('donor-parts-list')).toContainText('None yet');
});

test('the colours on the board and the labels in the list say what the plan said, and go neutral the moment the board changes', async ({ page }) => {
  await open(page);
  await page.getByTestId('donor-add-centre').click();
  await page.getByTestId('donor-marking').fill('NE555');
  await page.getByTestId('donor-plan').click();
  await viewerReady(page);
  const fill = () => page.getByTestId('donor-part-U1').locator('rect').getAttribute('fill');
  expect(await fill()).toBe('#3fb950');
  // A reading is not an identification: the label says so.
  await expect(page.getByTestId('donor-parts-list')).toContainText('Worth taking, if the marking checks out');
  await page.getByTestId('assembly-next').click();
  await expect(page.getByTestId('assembly-verdict')).toHaveText('Worth taking, if the marking checks out');
  await expect(page.getByTestId('assembly-checks')).toContainText('agrees with a datasheet');
  await expect(page.getByTestId('assembly-viewer')).not.toContainText('revision');
  await page.getByTestId('donor-marking').fill('');
  await expect(page.getByTestId('donor-stale')).toBeVisible();
  expect(await fill()).toBe('#7b8aa0');                                                  // not green any more: that was for the old marking
});

test('a file or stored board with hostile contents is cleaned or refused and never breaks the page', async ({ page }, testInfo) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.addInitScript(() => {
    try {
      if (!sessionStorage.getItem('__seeded')) {
        sessionStorage.setItem('__seeded', '1');
        // An old, partial and odd shape of saved board: no refs, a number where text belongs, a size that is an object.
        localStorage.setItem('hs-donor-capture-v1', JSON.stringify({ name: 'x', width_mm: 60, length_mm: 40, parts: [{ kind: 'ic', package: 'SOIC', x_mm: 10, y_mm: 10, ref: 123, width_mm: {}, marking: ['no'] }, { kind: 5, package: 'x', x_mm: 1, y_mm: 1 }] }));
      }
    } catch { /* ignore */ }
  });
  await page.setViewportSize({ width: 1500, height: 1000 });
  await page.goto(DONOR);
  await expect(page.getByTestId('donor-kind').locator('option')).not.toHaveCount(0, { timeout: 20000 });
  await expect(page.getByTestId('donor-parts-list').locator('li')).toHaveCount(1);       // the usable part is kept, the other is not
  await page.getByTestId('donor-add-centre').click();                                    // and adding to it still works
  await expect(page.getByTestId('donor-parts-list').locator('li')).toHaveCount(2);

  const huge = testInfo.outputPath('huge.json');
  fs.writeFileSync(huge, JSON.stringify({ name: 'x', board: { width_mm: 60, length_mm: 40 }, parts: Array.from({ length: 2000 }, () => ({ kind: 'ic', package: 'SOIC', x_mm: 10, y_mm: 10 })) }));
  await page.locator('input[type=file][accept*="json"]').setInputFiles(huge);
  await expect(page.getByTestId('donor-notice')).toContainText('Loaded 300 parts');
  await expect(page.getByTestId('donor-notice')).toContainText('1700 could not be read or were over the limit of 300');
  const wide = testInfo.outputPath('wide.json');
  fs.writeFileSync(wide, JSON.stringify({ name: 'x', board: { width_mm: 1e308, length_mm: 40 }, parts: [] }));
  await page.locator('input[type=file][accept*="json"]').setInputFiles(wide);
  await expect(page.getByTestId('donor-notice')).toContainText('not a board description');
  const hidden = testInfo.outputPath('hidden.json');
  fs.writeFileSync(hidden, JSON.stringify({ name: 'Router‮', board: { width_mm: 60, length_mm: 40 }, parts: [{ kind: 'ic', package: 'SOIC', x_mm: 10, y_mm: 10, ref: 'U1', marking: 'NE​555' }] }));
  await page.locator('input[type=file][accept*="json"]').setInputFiles(hidden);
  await expect(page.getByTestId('donor-name')).toHaveValue('Router');
  await page.getByTestId('donor-part-U1').click({ force: true });
  await expect(page.getByTestId('donor-marking')).toHaveValue('NE555');                  // the hidden characters are gone before they are shown
  expect(errors).toEqual([]);
});

test('arrow keys in the 3D view step the plan and never move or delete the part selected on the board', async ({ page }) => {
  await open(page);
  await page.getByTestId('donor-example').click();
  await page.getByTestId('donor-part-U3').click();
  const place = async () => { const rect = page.getByTestId('donor-part-U3').locator('rect'); return [await rect.getAttribute('x'), await rect.getAttribute('y')]; };   // board units, so scrolling cannot fool it
  const before = await place();
  await page.getByTestId('donor-plan').click();
  const viewer = await viewerReady(page);
  await viewer.focus();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  await expect(viewer).toHaveAttribute('data-step', '2');
  await page.keyboard.press('Delete');
  await expect(page.getByTestId('donor-part-U3')).toHaveCount(1);
  expect(await place()).toEqual(before);
});

test('starting again also clears the photo under the board', async ({ page }) => {
  await open(page);
  await page.getByTestId('donor-photo').setInputFiles({ name: 'board.png', mimeType: 'image/png', buffer: PNG });
  await expect(page.getByTestId('donor-canvas').locator('image')).toHaveCount(1);
  await page.getByTestId('donor-reset').click();
  await expect(page.getByTestId('donor-canvas').locator('image')).toHaveCount(0);
});
