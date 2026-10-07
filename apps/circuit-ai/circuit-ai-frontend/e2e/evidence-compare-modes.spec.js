const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const COMPARE = `${APP_URL}/engineering/evidence/compare?project=outsider-fixture&base=5&candidate=6`;

// Decode a screenshot inside the page and report how much of it is lit, so "identical parts cancel to black" is measured
// from what is actually drawn rather than assumed from the DOM.
async function litFraction(page, locator) {
  const png = await locator.screenshot();
  return page.evaluate(async (base64) => {
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/png' }));
    const canvas = document.createElement('canvas');
    canvas.width = bitmap.width; canvas.height = bitmap.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(bitmap, 0, 0);
    const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    let lit = 0;
    for (let i = 0; i < data.length; i += 4) if (Math.max(data[i], data[i + 1], data[i + 2]) > 70) lit += 1;
    return { lit, total: data.length / 4, fraction: lit / (data.length / 4) };
  }, png.toString('base64'));
}


async function openMode(page, name) {
  await page.getByRole('button', { name, exact: true }).click();
  await expect(page.getByTestId('comparison-viewer')).toHaveAttribute('data-mode', name.toLowerCase());
  await expect(page.locator('[data-testid="comparison-viewer"] kicanvas-embed:not([data-retired])')).toHaveCount(2, { timeout: 20000 });
  await expect(page.getByLabel('Loading the saved copies')).toHaveCount(0, { timeout: 20000 });
  await page.waitForTimeout(1200);
}

test('difference mode makes what is identical disappear and keeps what changed', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(COMPARE);
  await expect(page.getByRole('button', { name: 'Candidate', exact: true })).toHaveAttribute('aria-pressed', 'true');

  await openMode(page, 'Before');
  const before = await litFraction(page, page.getByTestId('comparison-stage'));

  await openMode(page, 'Difference');
  const difference = await litFraction(page, page.getByTestId('comparison-stage'));

  // The drawing alone lights a real share of the view; the difference of two near-identical revisions lights far less,
  // but not nothing: the resistor whose value changed is still there.
  expect(before.fraction).toBeGreaterThan(0.05);
  expect(difference.fraction).toBeLessThan(before.fraction / 20);
  expect(difference.lit).toBeGreaterThan(20);
});

test('the same file twice cancels completely in difference mode', async ({ page }) => {
  // Both revisions answer with revision 6's file, so there is nothing to show but black.
  await page.route('**/api/proxy/engineering/projects/outsider-fixture/revisions/5/artifacts/*/file', async (route) => {
    await route.fulfill({ response: await route.fetch({ url: route.request().url().replace('/revisions/5/', '/revisions/6/') }) });
  });
  await page.route('**/api/proxy/engineering/projects/outsider-fixture/artifact-diff*', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, diff: { ...body.diff, summary: { added: 0, removed: 0, changed: 0, unchanged: 1 }, changes: [] } } });
  });
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(COMPARE);
  await openMode(page, 'Difference');
  const result = await litFraction(page, page.getByTestId('comparison-stage'));
  expect(result.fraction).toBeLessThan(0.003);
});

test('swipe puts one revision on each side of a divider that can be dragged and moved with the keyboard', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(COMPARE);
  await openMode(page, 'Swipe');

  const divider = page.getByTestId('swipe-divider');
  await expect(divider).toHaveAttribute('aria-valuenow', '50');
  await divider.focus();
  await page.keyboard.press('ArrowRight');
  await expect(divider).toHaveAttribute('aria-valuenow', '53');
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowLeft');
  await expect(divider).toHaveAttribute('aria-valuenow', '47');

  const box = await divider.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 200, box.y + box.height / 2, { steps: 6 });
  await page.mouse.up();
  const moved = Number(await divider.getAttribute('aria-valuenow'));
  expect(moved).toBeGreaterThan(47);
});

test('both revisions share one camera, so panning or zooming one moves the other', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(COMPARE);
  await openMode(page, 'Swipe');

  const cameras = () => page.evaluate(() => {
    const [bottom, top] = Array.from(document.querySelectorAll('[data-testid="comparison-viewer"] kicanvas-embed:not([data-retired])'));
    const read = (embed) => { const c = embed.shadowRoot.querySelector('kc-schematic-app').viewer.viewport.camera; return { x: c.center.x, y: c.center.y, zoom: c.zoom }; };
    return { bottom: read(bottom), top: read(top) };
  });
  await page.evaluate(() => {
    const top = Array.from(document.querySelectorAll('[data-testid="comparison-viewer"] kicanvas-embed:not([data-retired])'))[1];
    const viewer = top.shadowRoot.querySelector('kc-schematic-app').viewer;
    viewer.viewport.camera.zoom = viewer.viewport.camera.zoom * 2.5;
    viewer.draw();
  });
  await expect.poll(async () => {
    const { bottom, top } = await cameras();
    return Math.abs(bottom.zoom - top.zoom) / top.zoom < 0.01 && Math.abs(bottom.x - top.x) < 0.5 && Math.abs(bottom.y - top.y) < 0.5;
  }, { timeout: 8000 }).toBe(true);
});

test('a revision with no retained file says so instead of showing something else', async ({ page }) => {
  await page.route('**/api/proxy/engineering/projects/outsider-fixture/revisions/5/artifacts/*/file', async (route) => {
    await route.fulfill({ status: 404, json: { detail: { type: 'artifact_not_retained', message: 'Revision 5 has no retained schematic.' } } });
  });
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(COMPARE);
  await page.getByRole('button', { name: 'Swipe', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: "Revision 5's schematic was not retained" })).toBeVisible({ timeout: 15000 });
  await expect(page.locator('[data-testid="comparison-viewer"] kicanvas-embed:not([data-retired])')).toHaveCount(0);
});

test('a viewer that was replaced before it finished loading never takes the place of the one that replaced it', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(COMPARE);
  await openMode(page, 'Swipe');

  // Ask for the board, then change your mind while it is still loading. Its load event arrives after the schematic is
  // already on screen, and must not mark itself live in the schematic's place. A slow CPU stretches the board's load
  // enough that this happens every time rather than only on a slow machine.
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 6 });
  await page.getByRole('button', { name: 'PCB', exact: true }).click();
  await page.waitForTimeout(260);
  await page.getByRole('button', { name: 'Schematic', exact: true }).click();
  await page.waitForTimeout(6000);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  await page.waitForTimeout(2500);

  await expect(page.getByLabel('Loading the saved copies')).toHaveCount(0);
  await expect(page.locator('[data-testid="comparison-viewer"] kicanvas-embed:not([data-retired])')).toHaveCount(2);
  await expect(page.locator('[data-testid="comparison-viewer"] kicanvas-embed[data-retired]')).toHaveCount(0, { timeout: 15000 });

  // And the two are still one view.
  await page.evaluate(() => {
    const top = Array.from(document.querySelectorAll('[data-testid="comparison-viewer"] kicanvas-embed:not([data-retired])'))[1];
    const viewer = top.shadowRoot.querySelector('kc-schematic-app').viewer;
    viewer.viewport.camera.zoom = viewer.viewport.camera.zoom * 2;
    viewer.draw();
  });
  await expect.poll(() => page.evaluate(() => {
    const [bottom, top] = Array.from(document.querySelectorAll('[data-testid="comparison-viewer"] kicanvas-embed:not([data-retired])'));
    const zoom = (embed) => embed.shadowRoot.querySelector('kc-schematic-app').viewer.viewport.camera.zoom;
    return Math.abs(zoom(bottom) - zoom(top)) / zoom(top) < 0.01;
  }), { timeout: 8000 }).toBe(true);
  expect(errors, `uncaught browser errors: ${errors.join(' | ')}`).toEqual([]);
});
