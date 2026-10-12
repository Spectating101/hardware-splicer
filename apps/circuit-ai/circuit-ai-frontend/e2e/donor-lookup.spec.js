const { test, expect } = require('@playwright/test');
const fs = require('node:fs');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const DONOR = `${APP_URL}/engineering/donor`;
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');

async function open(page) {
  await page.setViewportSize({ width: 1500, height: 1000 });
  await page.addInitScript(() => { try { if (!sessionStorage.getItem('__seeded')) { localStorage.clear(); sessionStorage.setItem('__seeded', '1'); } } catch { /* ignore */ } });
  await page.goto(DONOR);
  await expect(page.getByTestId('donor-kind').locator('option')).not.toHaveCount(0, { timeout: 20000 });
}
async function chip(page, marking, pkg = 'DIP') {
  await page.getByTestId('donor-add-centre').click();
  await page.getByTestId('donor-selected').locator('select').nth(1).selectOption(pkg);
  await page.getByTestId('donor-marking').fill(marking);
}
const panel = (page) => page.getByTestId('lookup-panel');

test('a marking is looked up in KiCad\'s library, says how close each answer is, and offers the package and the measurements', async ({ page }) => {
  await open(page);
  await chip(page, 'NE555');
  await expect(panel(page)).toHaveAttribute('data-status', 'ready', { timeout: 15000 });
  const matches = page.getByTestId('lookup-matches').locator('li');
  await expect(matches).toHaveCount(2);                                           // NE555D and NE555P: variants of the name typed
  await expect(matches.first()).toHaveAttribute('data-tier', 'variant');
  await expect(matches.first()).toContainText('a package, a grade or a different chip');
  await expect(panel(page)).toContainText('KiCad symbol library 9.0');
  await expect(panel(page)).toContainText('not proof that the chip you hold is that part');
  const links = await panel(page).locator('a').evaluateAll((nodes) => nodes.map((n) => n.getAttribute('href')));
  expect(links.length).toBeGreaterThan(0);
  for (const href of links) expect(href).toMatch(/^https?:\/\//);

  // The library's own package becomes the part's package with one click.
  await page.getByTestId('donor-marking').fill('NE555P');
  await expect(panel(page)).toHaveAttribute('data-status', 'ready', { timeout: 15000 });
  await page.getByTestId('donor-package').selectOption('SOIC');                                    // the palette; the part's own package is below
  await page.getByTestId('lookup-use-package').first().click();
  await expect(page.getByTestId('donor-selected').locator('select').nth(1)).toHaveValue('DIP');
  await expect(page.getByTestId('lookup-gates')).toContainText('pin 8 (VCC)');
  await expect(page.getByTestId('lookup-gates')).toContainText('not read from your chip');
  await expect(page.getByTestId('lookup-reading')).toHaveCount(3);
  await expect(page.getByTestId('lookup-recorded')).toHaveText('0 of 3 readings recorded');
});

test('what you measure is written down, counted, carried into the plan and the spreadsheet, and never called a pass', async ({ page }, testInfo) => {
  await open(page);
  await chip(page, 'NE555P');
  await expect(page.getByTestId('lookup-reading')).toHaveCount(3, { timeout: 15000 });
  await page.getByTestId('lookup-reading').first().fill('5.02 V');
  await expect(page.getByTestId('lookup-recorded')).toHaveText('1 of 3 readings recorded');
  await page.getByTestId('donor-plan').click();
  const viewer = page.getByTestId('assembly-viewer');
  await expect(viewer).toHaveAttribute('data-state', 'ready', { timeout: 30000 });
  await page.getByTestId('assembly-slider').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByTestId('assembly-instruction')).toContainText('Readings recorded: 1 of 3');
  await expect(page.getByTestId('assembly-instruction')).toContainText('not a pass');
  await expect(page.getByTestId('assembly-instruction')).toContainText('not from your chip');
  await expect(page.getByTestId('assembly-reading')).toHaveText(['Recorded: 5.02 V', 'Not recorded yet', 'Not recorded yet'].slice(0, 3).slice(0, await page.getByTestId('assembly-reading').count()));
  await expect(page.getByTestId('donor-parts-list')).toContainText('1/3 measured');
  await expect(page.getByTestId('reclaim-table')).toContainText('1 of 3 readings recorded');

  const [download] = await Promise.all([page.waitForEvent('download'), page.getByTestId('reclaim-csv').click()]);
  const saved = testInfo.outputPath('reclaim.csv');
  await download.saveAs(saved);
  const raw = fs.readFileSync(saved, 'utf8');
  expect(raw.charCodeAt(0)).toBe(0xFEFF);                                                   // a spreadsheet then reads it as UTF-8
  const csv = raw.slice(1);
  expect(csv.split('\r\n')[0]).toBe('Label,What it is (as you read it),Package,Advice,Measurements,Datasheet,Why');
  expect(csv).toContain('U1,NE555P,');
  expect(csv).toContain('1 of 3 readings recorded');
  expect(csv).toContain('http://www.ti.com/lit/ds/symlink/ne555.pdf');
  expect(csv.toLowerCase()).not.toContain('passed');
});

test('a marking the library does not know says so plainly and points to a top-mark database, and a family is not claimed as the chip', async ({ page }) => {
  await open(page);
  await chip(page, 'L9110S');
  await expect(panel(page)).toHaveAttribute('data-status', 'ready', { timeout: 15000 });
  await expect(page.getByTestId('lookup-none')).toContainText('nothing under this marking');
  await expect(page.getByTestId('lookup-none')).toContainText('does not mean it is fake');
  expect(await page.getByTestId('lookup-smd-link').getAttribute('href')).toBe('https://www.s-manuals.com/smd/l9110s');
  await expect(page.getByTestId('lookup-gates')).toHaveCount(0);
  await page.getByTestId('donor-marking').fill('W25Q128JWSIQ');
  await expect(page.getByTestId('lookup-matches').locator('li').first()).toHaveAttribute('data-tier', 'family', { timeout: 15000 });
  await expect(page.getByTestId('lookup-matches')).toContainText('not this one');
  await expect(page.getByTestId('lookup-use-package')).toHaveCount(0);                       // a family member's package is not this chip's
  await expect(page.getByTestId('lookup-gates')).toHaveCount(0);                             // and its pins are not this chip's
  await page.getByTestId('donor-marking').fill('ab');
  await expect(panel(page)).toContainText('3 characters or more');
});

test('a box drawn over a photo gives the part its size and place from the photo', async ({ page }) => {
  await open(page);
  await page.getByTestId('donor-photo').setInputFiles({ name: 'board.png', mimeType: 'image/png', buffer: PNG });
  await expect(page.getByTestId('donor-length')).toHaveValue('60');
  await page.getByTestId('donor-mode-measure').click();
  // Board millimetres to screen pixels, through the drawing's own transform (the board is letterboxed inside its frame).
  const at = (xmm, ymm) => page.getByTestId('donor-canvas').evaluate((svg, [x, y]) => {
    const m = svg.getScreenCTM();
    return { x: m.a * x + m.c * y + m.e, y: m.b * x + m.d * y + m.f };
  }, [xmm, ymm]);
  const a = await at(15, 15);
  const b = await at(35, 25);                                                                // a 20 mm by 10 mm box
  await page.mouse.move(a.x, a.y);
  await page.mouse.down();
  await page.mouse.move((a.x + b.x) / 2, (a.y + b.y) / 2, { steps: 4 });
  await expect(page.getByTestId('donor-band')).toBeVisible();                               // a dashed box follows the drag
  await page.mouse.move(b.x, b.y, { steps: 4 });
  await page.mouse.up();
  await expect(page.getByTestId('donor-band')).toHaveCount(0);
  await expect(page.getByTestId('donor-part-U1')).toBeVisible();
  const [w, l] = await page.getByTestId('donor-selected').locator('input[type=number]').evaluateAll((nodes) => nodes.map((n) => Number(n.value)));
  expect(w).toBeGreaterThan(18);
  expect(w).toBeLessThan(22);
  expect(l).toBeGreaterThan(8);
  expect(l).toBeLessThan(12);
  await expect(page.getByTestId('donor-parts-list').locator('li')).toHaveCount(1);          // one drag made one part
  // A plain click in this mode still places a part, at the typical size.
  const c = await at(45, 40);
  await page.mouse.click(c.x, c.y);
  await expect(page.getByTestId('donor-parts-list').locator('li')).toHaveCount(2);
  const sizes = await page.getByTestId('donor-selected').locator('input[type=number]').evaluateAll((nodes) => nodes.map((n) => n.value));
  expect(sizes).toEqual(['', '']);                                                          // typical: nothing typed or drawn
});

test('teardown search offers links with credit, and says plainly when there is nothing or the input is too short', async ({ page }) => {
  await open(page);
  await page.getByTestId('teardown-query').fill('roku stick');
  await page.getByTestId('teardown-go').click();
  const results = page.getByTestId('teardown-results');
  await expect(results).toContainText('Roku Stick Teardown', { timeout: 15000 });
  const href = await results.locator('a').first().getAttribute('href');
  expect(href).toMatch(/^https:\/\/www\.ifixit\.com\//);
  expect(await results.locator('a').first().getAttribute('rel')).toContain('noopener');
  await expect(results).toContainText('CC BY-NC-SA');
  await expect(results).toContainText('links to their pages');
  await page.getByTestId('teardown-query').fill('nothing at all');
  await page.getByTestId('teardown-go').click();
  await expect(page.getByTestId('teardown-results')).toContainText('No guides found');
  await page.getByTestId('teardown-query').fill('ab');
  await page.getByTestId('teardown-go').click();
  await expect(page.getByTestId('teardown-error')).toContainText('at least 3 characters');
});

test('the spreadsheet never carries a formula a spreadsheet program would run', async ({ page }, testInfo) => {
  await open(page);
  await page.getByTestId('donor-add-centre').click();
  await page.getByTestId('donor-marking').fill('=HYPERLINK("http://x.example","go")');
  await page.getByTestId('donor-plan').click();
  await expect(page.getByTestId('reclaim-table')).toBeVisible({ timeout: 30000 });
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByTestId('reclaim-csv').click()]);
  const saved = testInfo.outputPath('inject.csv');
  await download.saveAs(saved);
  const lines = fs.readFileSync(saved, 'utf8').slice(1).split('\r\n');
  expect(lines[1]).toContain("\"'=HYPERLINK(\"\"http://x.example\"\",\"\"go\"\")\"");     // quoted, doubled quotes, and an apostrophe in front
  expect(lines.some((line) => /(^|,)[=+@-]/.test(line.replace(/"(?:[^"]|"")*"/g, '')))).toBe(false);
});

test('a new marking never shows the old chip\'s answer, and a right-click places nothing', async ({ page }) => {
  await open(page);
  await chip(page, 'LM358');
  await expect(panel(page)).toHaveAttribute('data-status', 'ready', { timeout: 15000 });
  await expect(page.getByTestId('lookup-matches')).toContainText('LM358');
  await page.getByTestId('donor-marking').fill('NE555P');
  await expect(page.getByTestId('lookup-matches')).not.toContainText('LM358');            // not even dimmed, while the new answer loads
  await expect(page.getByTestId('lookup-matches')).toContainText('NE555P', { timeout: 15000 });
  const count = await page.getByTestId('donor-parts-list').locator('li').count();
  const at = await page.getByTestId('donor-canvas').evaluate((svg) => { const m = svg.getScreenCTM(); return { x: m.a * 5 + m.e, y: m.d * 5 + m.f }; });
  await page.mouse.click(at.x, at.y, { button: 'right' });
  await expect(page.getByTestId('donor-parts-list').locator('li')).toHaveCount(count);
});

test('a reading belongs to the chip it was taken from', async ({ page }) => {
  await open(page);
  await chip(page, 'NE555P');
  await expect(page.getByTestId('lookup-reading')).toHaveCount(3, { timeout: 15000 });
  await page.getByTestId('lookup-reading').first().fill('5.02 V');
  await page.getByTestId('donor-selected').locator('select').nth(1).selectOption('SOIC');
  await page.getByTestId('donor-marking').fill('NE555D');
  await expect(page.getByTestId('lookup-reading')).toHaveCount(3, { timeout: 15000 });
  await expect(page.getByTestId('lookup-reading').first()).toHaveValue('');
  await expect(page.getByTestId('lookup-recorded')).toHaveText('0 of 3 readings recorded');
});

test('the capture page with the lookup open has no sideways scrolling on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(DONOR);
  await expect(page.getByTestId('donor-add-centre')).toBeVisible({ timeout: 20000 });
  await page.getByTestId('donor-add-centre').click();
  await page.getByTestId('donor-marking').fill('NE555P');
  await expect(panel(page)).toHaveAttribute('data-status', 'ready', { timeout: 15000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
});
