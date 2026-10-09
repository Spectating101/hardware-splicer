const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const DEVICE = `${APP_URL}/engineering/device`;

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

async function open(page) {
  await page.setViewportSize({ width: 1500, height: 1000 });
  await page.goto(DEVICE);
  const viewer = page.getByTestId('device-viewer');
  await expect(viewer).toHaveAttribute('data-ready', '1', { timeout: 40000 });
  await settle(viewer);
  return viewer;
}
async function settle(viewer) {
  await expect(viewer).toHaveAttribute('data-moving', '0', { timeout: 20000 });
  await viewer.page().waitForTimeout(200);
}
async function next(page, viewer, times = 1) {
  for (let i = 0; i < times; i += 1) {
    await page.getByTestId('device-next').click();
    await settle(viewer);
  }
}

test('the whole gadget goes together on screen: parts hover apart, the board drops in, wires grow pin to pin, the lid comes down and USB plugs in', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const viewer = await open(page);
  const stage = viewer.locator('canvas');

  await expect(page.getByTestId('device-counter')).toHaveText(/Step 1 of 12/);
  await expect(viewer).toHaveAttribute('data-mcu', 'away');
  await expect(viewer).toHaveAttribute('data-lid', 'open');
  await expect(viewer).toHaveAttribute('data-wires', '0');
  await expect(page.getByTestId('device-label')).toHaveCount(4);   // the board, the display, the lid and the base are named
  const exploded = await pixels(stage);

  await next(page, viewer, 2);                                     // measure, then place the board
  await expect(page.getByTestId('device-title')).toContainText('Lay the ESP32');
  await expect(viewer).toHaveAttribute('data-mcu', 'home');
  await expect(page.getByTestId('device-label')).toHaveCount(2);   // the USB end and the antenna end
  const placed = await pixels(stage);
  expect(await differing(page, exploded, placed)).toBeGreaterThan(500);

  // Four wires, one step each, and the pins at both ends are named.
  const seen = [];
  for (let i = 1; i <= 4; i += 1) {
    await next(page, viewer);
    await expect(viewer).toHaveAttribute('data-wires', String(i));
    seen.push(await page.getByTestId('device-title').innerText());
    await expect(page.getByTestId('device-label')).toHaveCount(2);
  }
  expect(seen).toEqual(['Connect display.VCC to mcu.3V3', 'Connect display.GND to mcu.GND', 'Connect display.SCL to mcu.IO22', 'Connect display.SDA to mcu.IO21']);
  await expect(page.getByTestId('device-instruction')).toContainText('IO21');
  await expect(page.getByTestId('device-instruction')).toContainText('header J3, pin 6');
  await expect(viewer).toHaveAttribute('data-display', 'home');

  await next(page, viewer);                                        // the check before power
  await expect(page.getByTestId('device-checks')).toContainText('NOT connected');
  await next(page, viewer);                                        // display into the lid
  await expect(viewer).toHaveAttribute('data-lid', 'hover');
  await next(page, viewer);                                        // close
  await expect(viewer).toHaveAttribute('data-lid', 'closed');
  await expect(viewer).toHaveAttribute('data-usb', 'out');
  await next(page, viewer);                                        // power
  await expect(viewer).toHaveAttribute('data-usb', 'in');
  await expect(page.getByTestId('device-checks')).toContainText('between 3.0 V and 3.6 V');
  await next(page, viewer);                                        // test
  await expect(page.getByTestId('device-instruction')).toContainText('0x3C');
  await expect(page.getByTestId('device-next')).toBeDisabled();
  const finished = await pixels(stage);
  expect(await differing(page, placed, finished)).toBeGreaterThan(500);   // wires, display, lid and cable are really drawn
  expect(errors).toEqual([]);
});

test('stepping back takes things out again, and play, keys and the slider move through the build', async ({ page }) => {
  const viewer = await open(page);
  await page.getByTestId('device-slider').focus();
  await page.keyboard.press('End');
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-wires', '4');
  await expect(viewer).toHaveAttribute('data-lid', 'closed');
  await page.keyboard.press('Home');
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-wires', '0');
  await expect(viewer).toHaveAttribute('data-lid', 'open');
  await expect(viewer).toHaveAttribute('data-mcu', 'away');

  await page.getByTestId('device-play').click();
  await expect(page.getByTestId('device-play')).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(async () => Number(await viewer.getAttribute('data-step')), { timeout: 20000 }).toBeGreaterThanOrEqual(3);
  await page.getByTestId('device-play').click();
  const stopped = await viewer.getAttribute('data-step');
  await page.waitForTimeout(2500);
  expect(await viewer.getAttribute('data-step')).toBe(stopped);
  await viewer.focus();
  await page.keyboard.press('ArrowLeft');
  await expect(viewer).toHaveAttribute('data-step', String(Number(stopped) - 1));
});

test('wiring that is wrong is caught and explained, and the example comes back', async ({ page }) => {
  const viewer = await open(page);
  await expect(page.getByTestId('device-findings')).toContainText('nothing wrong');
  const editor = page.getByTestId('device-spec-editor');
  const good = await editor.inputValue();

  // SDA onto a pin that belongs to the module's flash memory.
  await editor.fill(good.replace('"mcu.IO21"', '"mcu.D2"'));
  await page.getByTestId('device-spec-apply').click();
  const finding = page.locator('[data-rule="flash_pin"]');
  await expect(finding).toBeVisible({ timeout: 15000 });
  await expect(finding).toHaveAttribute('data-severity', 'error');
  await expect(finding).toContainText('flash memory');
  await expect(finding).toContainText('Basis:');
  await expect(page.getByTestId('device-problems')).toContainText('1 wiring problem');

  // 5 V onto the display's supply is a warning, not a stop.
  await editor.fill(good.replace('"mcu.3V3"', '"mcu.5V"'));
  await page.getByTestId('device-spec-apply').click();
  await expect(page.locator('[data-rule="five_volts_to_a_3v3_system"]')).toHaveAttribute('data-severity', 'warning');

  // A missing wire is a problem; a spec the planner cannot read is explained, not swallowed.
  const spec = JSON.parse(good);
  spec.connections = spec.connections.slice(0, 3);
  await editor.fill(JSON.stringify(spec));
  await page.getByTestId('device-spec-apply').click();
  await expect(page.locator('[data-rule="missing_connection"]')).toBeVisible({ timeout: 15000 });

  await editor.fill('{ not json');
  await page.getByTestId('device-spec-apply').click();
  await expect(page.getByTestId('device-error')).toContainText('not valid JSON');
  spec.connections.push({ from: 'display.NOPE', to: 'mcu.3V3' });
  await editor.fill(JSON.stringify(spec));
  await page.getByTestId('device-spec-apply').click();
  await expect(page.getByTestId('device-error')).toContainText('no pin named');

  await page.getByRole('button', { name: 'Back to the example' }).click();
  await expect(page.getByTestId('device-findings')).toContainText('nothing wrong', { timeout: 15000 });
  await expect(viewer).toHaveAttribute('data-ready', '1');
  await expect(page.getByTestId('device-counter')).toHaveText(/Step 1 of 12/);
});

test('every number says where it came from, and what is only typical says so', async ({ page }) => {
  await open(page);
  const sources = page.getByTestId('device-sources');
  await expect(sources.locator('a')).toHaveCount(7);
  for (const link of await sources.locator('a').all()) expect(await link.getAttribute('href')).toMatch(/^https:\/\//);
  await expect(sources).toContainText('read 2026-10-09');
  await expect(sources).toContainText('ESP32-DevKitC V4 dimensions drawing');
  const measure = page.getByTestId('device-measure');
  await expect(measure).toContainText('has not been printed or test-fitted');
  await expect(measure).toContainText('Measure yours');
  await expect(page.getByTestId('device-shopping')).toContainText('check the version');
  await expect(page.getByTestId('device-panel')).toContainText('approves building');
});

test('a phone-sized screen has no sideways scrolling and still shows the animation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(DEVICE);
  const viewer = page.getByTestId('device-viewer');
  await expect(viewer).toHaveAttribute('data-ready', '1', { timeout: 40000 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  const box = await viewer.boundingBox();
  expect(box.width).toBeGreaterThan(300);
  expect(box.height).toBeGreaterThan(500);
});

test('leaving the page releases the graphics context', async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    window.__contexts = [];
    HTMLCanvasElement.prototype.getContext = function (kind, ...rest) {
      const context = original.call(this, kind, ...rest);
      if (context && String(kind).startsWith('webgl') && document.querySelector('[data-testid="device-viewer"]')) window.__contexts.push(context);
      return context;
    };
  });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await open(page);
  expect(await page.evaluate(() => window.__contexts.length)).toBeGreaterThan(0);
  await page.getByRole('link', { name: 'Project review' }).click();
  await expect(page.getByTestId('device-viewer')).toHaveCount(0);
  const lost = await page.evaluate(() => window.__contexts.map((context) => context.isContextLost()));
  expect(lost.every(Boolean)).toBe(true);
  expect(errors).toEqual([]);
});
