const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const EVIDENCE = `${APP_URL}/engineering/evidence?project=outsider-fixture`;

async function pixels(locator) {
  return (await locator.screenshot()).toString('base64');
}
async function differing(page, a, b) {
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
    let count = 0;
    for (let i = 0; i < one.length; i += 4) if (Math.abs(one[i] - two[i]) + Math.abs(one[i + 1] - two[i + 1]) + Math.abs(one[i + 2] - two[i + 2]) > 40) count += 1;
    return count;
  }, [a, b]);
}
async function settle(viewer) {
  await expect(viewer).toHaveAttribute('data-flying', '0', { timeout: 20000 });
  await viewer.page().waitForTimeout(250);
}
async function openSalvage(page) {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(EVIDENCE);
  await page.getByTestId('assemble-tab').click();
  const viewer = page.getByTestId('assembly-viewer');
  await expect(viewer).toHaveAttribute('data-state', 'ready', { timeout: 30000 });
  await settle(viewer);
  await page.getByTestId('assembly-mode-salvage').click();
  await expect(viewer).toHaveAttribute('data-mode', 'salvage');
  await expect(viewer).toHaveAttribute('data-state', 'ready', { timeout: 30000 });
  await expect(viewer.locator('canvas')).toBeVisible({ timeout: 30000 });
  await settle(viewer);
  return viewer;
}

test('taking the board apart: safety first, then the parts worth keeping lift off in order, and what is left stays on the board', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const viewer = await openSalvage(page);
  const stage = viewer.locator('canvas');

  await expect(page.getByTestId('assembly-counter')).toHaveText(/Step 1 of 7/);
  await expect(page.getByTestId('assembly-title')).toHaveText('Make the board safe to work on');
  await expect(page.getByTestId('assembly-instruction')).toContainText('discharge');
  await expect(viewer).toHaveAttribute('data-placed', '38');       // every fitted part is on the board; R1 and R4 are not fitted
  await expect(viewer).toHaveAttribute('data-removed', '0');
  const before = await pixels(stage);

  await page.getByTestId('assembly-next').click();
  await expect.poll(async () => Number(await viewer.getAttribute('data-flying')), { timeout: 4000 }).toBeGreaterThan(0);   // it is really lifting off
  await settle(viewer);
  await expect(page.getByTestId('assembly-title')).toContainText('Remove the connector JP1');
  await expect(page.getByTestId('assembly-verdict')).toHaveAttribute('data-verdict', 'optional');
  await expect(page.getByTestId('assembly-verdict')).toHaveText('Cheap to buy new');
  await expect(viewer).toHaveAttribute('data-removed', '1');
  await expect(viewer).toHaveAttribute('data-placed', '37');

  // The chips the board file names are worth taking, and the reason is the file's own words.
  await page.getByTestId('assembly-slider').focus();
  for (let i = 0; i < 2; i += 1) await page.keyboard.press('ArrowRight');
  await settle(viewer);
  await expect(page.getByTestId('assembly-verdict')).toHaveAttribute('data-verdict', 'keep');
  await expect(page.getByTestId('assembly-title')).toContainText('chip');
  await expect(page.getByTestId('assembly-instruction')).toContainText('names it');
  await expect(page.getByTestId('assembly-checks')).toContainText('read the text printed on the chip');

  await page.keyboard.press('End');
  await settle(viewer);
  await expect(page.getByTestId('assembly-title')).toHaveText('Sort, label and test what you kept');
  await expect(viewer).toHaveAttribute('data-removed', '5');
  await expect(viewer).toHaveAttribute('data-placed', '33');       // 33 parts are left on the board
  await expect(page.getByTestId('assembly-instruction')).toContainText('Nothing you took is known to work');
  const after = await pixels(stage);
  expect(await differing(page, before, after)).toBeGreaterThan(400);
  expect(errors).toEqual([]);
});

test('the summary, the limits and the authority line say what this plan is and is not', async ({ page }) => {
  const viewer = await openSalvage(page);
  await expect(page.getByTestId('salvage-summary')).toHaveText('3 worth taking · 0 take it, test first · 0 read the marking · 2 cheap to buy new · 33 leave it');
  const limits = page.getByTestId('salvage-limits');
  await expect(limits).toContainText("Needs the board's file");
  await expect(limits).toContainText('never a guess');
  await expect(limits).toContainText('unknown until it is tested');
  await expect(page.getByTestId('assembly-panel')).toContainText('measures nothing');
  await expect(page.getByTestId('assembly-not-fitted')).toContainText('R1, R4');
  await expect(viewer).toHaveAttribute('data-mode', 'salvage');
});

test('switching between putting the board together and taking it apart changes the whole sequence and nothing is left over', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const viewer = await openSalvage(page);
  await page.getByTestId('assembly-mode-build').click();
  await expect(viewer).toHaveAttribute('data-mode', 'build');
  await expect(page.getByTestId('assembly-counter')).toHaveText(/Step 1 of 12/, { timeout: 30000 });
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-placed', '5');
  await expect(page.getByTestId('salvage-summary')).toHaveCount(0);
  await page.getByTestId('assembly-mode-salvage').click();
  await expect(page.getByTestId('assembly-counter')).toHaveText(/Step 1 of 7/, { timeout: 30000 });
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-placed', '38');
  expect(errors).toEqual([]);
});
