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
  await expect(page.getByTestId('device-checks')).toContainText('record what you observe; this plan supplies no reading');
  await next(page, viewer);                                        // display into the lid
  await expect(viewer).toHaveAttribute('data-lid', 'hover');
  await next(page, viewer);                                        // close
  await expect(viewer).toHaveAttribute('data-lid', 'closed');
  await expect(viewer).toHaveAttribute('data-usb', 'out');
  await next(page, viewer);                                        // power
  await expect(viewer).toHaveAttribute('data-usb', 'in');
  await expect(page.getByTestId('device-checks')).toContainText('record what you observe; this plan supplies no reading');
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

test('choosing the other pin order moves the wire', async ({ page }) => {
  const viewer = await open(page);
  const findings = page.getByTestId('device-findings');
  await expect(findings).toContainText('nothing wrong');
  await expect(findings).toContainText('These are the checks this tool makes');
  await expect(findings).toContainText('a wire that passes them is not a wire that works');
  await expect(page.locator('[data-rule="pin_order_assumed"]')).toBeVisible();
  await next(page, viewer, 3);
  await expect(viewer).toHaveAttribute('data-wires', '1');
  const before = await viewer.getAttribute('data-display-vcc-pad');
  expect(before).toBeTruthy();
  const control = page.getByTestId('device-pin-order');
  await expect(control).toHaveAccessibleName('Which order is printed on your module?');
  const options = await control.locator('option').evaluateAll((elements) => elements.map((element) => ({ id: element.value, label: element.textContent })));
  expect(options).toHaveLength(2);
  expect(options.some((option) => option.label.includes('AZ-Delivery'))).toBe(true);
  expect(options.some((option) => option.label.includes('DisplayModule'))).toBe(true);
  const selected = await control.inputValue();
  const other = options.find((option) => option.id !== selected).id;
  await control.selectOption(other);
  await expect(viewer).not.toHaveAttribute('data-display-vcc-pad', before, { timeout: 15000 });
  await expect(page.locator('[data-rule="pin_order_drawn"]')).toBeVisible();
  await expect(page.locator('[data-rule="pin_order_assumed"]')).toHaveCount(0);
  const spec = JSON.parse(await page.getByTestId('device-spec-editor').inputValue());
  expect(spec.modules.find((module) => module.id === 'display').pin_order).toBe(other);
  await expect(viewer).toHaveAttribute('data-ready', '1');
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-step', '0');
  await next(page, viewer, 3);
  await expect(viewer).toHaveAttribute('data-wires', '1');
  await expect(page.getByTestId('device-label')).toHaveCount(2);
  expect(Number(await viewer.getAttribute('data-wire-lag'))).toBeLessThan(0.3);
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
  // The flash pin is wrong, and the SDA wire that was rejected leaves the display without a working SDA: two problems.
  await expect(page.getByTestId('device-problems')).toContainText('2 wiring problems');
  await expect(page.locator('[data-rule="missing_connection"]')).toContainText('SDA');

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
  await expect(sources.locator('a')).toHaveCount(9);
  for (const link of await sources.locator('a').all()) expect(await link.getAttribute('href')).toMatch(/^https:\/\//);
  await expect(sources).toContainText('read 2026-10-09');
  await expect(sources).toContainText('ESP32-DevKitC V4 dimensions drawing');
  await expect(sources).toContainText('ESP32 Series Datasheet v5.3');
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


test('an oversized spec is refused by the page with a plain message, and the example still works afterwards', async ({ page }) => {
  const viewer = await open(page);
  const editor = page.getByTestId('device-spec-editor');
  const good = await editor.inputValue();
  await editor.fill(JSON.stringify({ ...JSON.parse(good), name: 'x'.repeat(70000) }));
  await page.getByTestId('device-spec-apply').click();
  await expect(page.getByTestId('device-error')).toContainText('at most 65536 bytes');
  // And it is a real HTTP 413, not a 200 that merely says so.
  const direct = await page.request.post(`${APP_URL}/api/proxy/engineering/devices/plan`, { data: 'x'.repeat(70000), headers: { 'content-type': 'application/json' } });
  expect(direct.status()).toBe(413);
  await editor.fill(good);
  await page.getByTestId('device-spec-apply').click();
  await expect(page.getByTestId('device-findings')).toContainText('nothing wrong');
  await expect(viewer).toHaveAttribute('data-ready', '1');
});

test('while the display descends to be wired, each wire stays attached to it', async ({ page }) => {
  const viewer = await open(page);
  await next(page, viewer, 2);                          // the board is in; the display is still hovering above
  await expect(viewer).toHaveAttribute('data-display', 'away');
  await page.getByTestId('device-next').click();        // wire 1: the display comes down while the wire grows
  await expect(viewer).toHaveAttribute('data-display', 'home');
  await expect(viewer).toHaveAttribute('data-moving', '1');
  // Sampled mid-flight: the wire is being redrawn from where the display is now, so it never lags behind it.
  const lags = [];
  for (let i = 0; i < 12; i += 1) {
    lags.push(Number(await viewer.getAttribute('data-wire-lag')));
    await page.waitForTimeout(60);
  }
  expect(Math.max(...lags)).toBeLessThan(0.3);       // millimetres between the wire's ends and its housings, while everything moves
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-wires', '1');
  expect(Number(await viewer.getAttribute('data-wire-lag'))).toBeLessThan(0.3);
});

async function sensorExample(page, viewer) {
  await page.getByTestId('device-example').selectOption('esp32_oled_bme280_usb');
  await expect(viewer).toHaveAttribute('data-step-count', '17', { timeout: 15000 });
  await expect(viewer).toHaveAttribute('data-rendered-modules', JSON.stringify(['mcu', 'display', 'sensor']));
  await expect(viewer).toHaveAttribute('data-ready', '1');
  await settle(viewer);
  return JSON.parse(await page.getByTestId('device-spec-editor').inputValue());
}

for (const sensor of [
  { id: 'adafruit-bme280-stemma-qt', name: 'BME280', power: 'Vin', clock: 'SCK', data: 'SDI', address: '0x77', sources: 12 },
  { id: 'adafruit-bh1750-stemma-qt', name: 'BH1750', power: 'VIN', clock: 'SCL', data: 'SDA', address: '0x23', sources: 12 },
  { id: 'adafruit-ds3231-stemma-qt', name: 'DS3231', power: 'Vin', clock: 'SCL', data: 'SDA', address: '0x68', sources: 13 },
]) {
  test(`${sensor.name} is a third drawn part, its wires follow its own group, and its scan remains an observation`, async ({ page }, testInfo) => {
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    const viewer = await open(page);
    const spec = await sensorExample(page, viewer);
    if (sensor.name !== 'BME280') {
      spec.modules.find((module) => module.id === 'sensor').module = sensor.id;
      spec.connections = spec.connections.map((wire) => ({ ...wire, from: wire.from.replace('sensor.Vin', `sensor.${sensor.power}`).replace('sensor.SCK', `sensor.${sensor.clock}`).replace('sensor.SDI', `sensor.${sensor.data}`) }));
      await page.getByTestId('device-spec-editor').fill(JSON.stringify(spec));
      await page.getByTestId('device-spec-apply').click();
      await expect(page.getByTestId('device-shopping')).toContainText(sensor.name);
      await expect(viewer).toHaveAttribute('data-ready', '1');
      await settle(viewer);
    }
    await expect(viewer).toHaveAttribute('data-modules', JSON.stringify({ mcu: 'away', display: 'away', sensor: 'away' }));
    await expect(page.getByTestId('device-label')).toHaveCount(5);
    await expect(page.getByTestId('device-label').filter({ hasText: sensor.name })).toHaveCount(1);
    await expect(page.getByTestId('device-pin-order')).toHaveCount(1); // Only the OLED has a published choice.
    await expect(page.getByTestId('device-sources').locator('a')).toHaveCount(sensor.sources);
    await expect(viewer).toContainText('Sensor pin positions are illustrative');
    await next(page, viewer, 2);
    await expect(viewer).toHaveAttribute('data-modules', JSON.stringify({ mcu: 'home', display: 'away', sensor: 'away' }));
    const before = await pixels(viewer.locator('canvas'));
    await next(page, viewer);
    await expect(page.getByTestId('device-title')).toContainText(sensor.name);
    await expect(viewer).toHaveAttribute('data-modules', JSON.stringify({ mcu: 'home', display: 'away', sensor: 'home' }));
    await expect(page.locator('[data-testid="device-label"][data-module="sensor"]')).toContainText('printed pin names');
    expect(await differing(page, before, await pixels(viewer.locator('canvas')))).toBeGreaterThan(100);
    // All eight wires, including sensor endpoints, really grow and remain attached.
    for (let number = 1; number <= 8; number += 1) {
      await next(page, viewer);
      await expect(viewer).toHaveAttribute('data-wires', String(number));
      await expect(page.getByTestId('device-label')).toHaveCount(2);
      expect(Number(await viewer.getAttribute('data-wire-lag'))).toBeLessThan(0.3);
    }
    await expect(page.locator('[data-testid="device-label"][data-module="sensor"]')).toContainText(sensor.data);
    await page.getByTestId('device-slider').focus();
    await page.keyboard.press('End');
    await settle(viewer);
    await expect(page.getByTestId('device-instruction')).toContainText(sensor.address);
    await expect(page.getByTestId('device-checks')).toContainText('record what you observe; this plan supplies no reading');
    await expect(page.getByTestId('device-panel')).toContainText('Nothing here approves building, powering or releasing');
    await testInfo.attach(`${sensor.name}-desktop`, { body: await viewer.screenshot(), contentType: 'image/png' });
    // Use the real range control's keyboard event to exercise React, not a synthetic scene API.
    await page.keyboard.press('Home');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await settle(viewer);
    await expect(viewer).toHaveAttribute('data-wires', '0');
    await expect(viewer).toHaveAttribute('data-modules', JSON.stringify({ mcu: 'home', display: 'away', sensor: 'away' }));
    expect(errors).toEqual([]);
  });
}

test('module IDs, including lid, are not mistaken for scene roles', async ({ page }) => {
  const viewer = await open(page);
  const spec = await sensorExample(page, viewer);
  const refs = { mcu: 'controller', display: 'screen', sensor: 'lid' };
  spec.modules = spec.modules.map((module) => ({ ...module, id: refs[module.id] }));
  spec.connections = spec.connections.map((wire) => Object.fromEntries(Object.entries(wire).map(([key, endpoint]) => {
    const [ref, pin] = endpoint.split('.');
    return [key, `${refs[ref]}.${pin}`];
  })));
  await page.getByTestId('device-spec-editor').fill(JSON.stringify(spec));
  await page.getByTestId('device-spec-apply').click();
  await expect(viewer).toHaveAttribute('data-rendered-modules', JSON.stringify(['controller', 'screen', 'lid']));
  await expect(viewer).toHaveAttribute('data-ready', '1');
  await next(page, viewer, 4);
  await expect(page.getByTestId('device-title')).toContainText('screen.VCC');
  expect(Number(await viewer.getAttribute('data-wire-lag'))).toBeLessThan(0.3);
  await page.getByTestId('device-slider').focus();
  await page.keyboard.press('End');
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-modules', JSON.stringify({ controller: 'home', screen: 'home', lid: 'home' }));
});

test('two breakouts are placed independently and an address conflict never plugs in USB', async ({ page }) => {
  const viewer = await open(page);
  const spec = await sensorExample(page, viewer);
  spec.modules.push({ id: 'sensor2', module: 'adafruit-bme280-stemma-qt' });
  spec.connections.push(...spec.connections.filter((wire) => wire.from.startsWith('sensor.')).map((wire) => ({ ...wire, from: wire.from.replace('sensor.', 'sensor2.') })));
  await page.getByTestId('device-spec-editor').fill(JSON.stringify(spec));
  await page.getByTestId('device-spec-apply').click();
  await expect(viewer).toHaveAttribute('data-rendered-modules', JSON.stringify(['mcu', 'display', 'sensor', 'sensor2']));
  await expect(page.locator('[data-rule="i2c_address_overlap"]')).toBeVisible();
  await expect(viewer).toHaveAttribute('data-ready', '1');
  await next(page, viewer, 3);
  await expect(viewer).toHaveAttribute('data-modules', JSON.stringify({ mcu: 'home', display: 'away', sensor: 'home', sensor2: 'away' }));
  await next(page, viewer);
  await expect(viewer).toHaveAttribute('data-modules', JSON.stringify({ mcu: 'home', display: 'away', sensor: 'home', sensor2: 'home' }));
  await page.getByTestId('device-slider').focus();
  await page.keyboard.press('End');
  await settle(viewer);
  await expect(viewer).toHaveAttribute('data-wires', '12');
  await expect(viewer).toHaveAttribute('data-usb', 'out');
  expect(Number(await viewer.getAttribute('data-wire-lag'))).toBeLessThan(0.3);
});

test('the sensor example fits a phone and can return to the unchanged OLED example', async ({ page }, testInfo) => {
  const viewer = await open(page);
  await sensorExample(page, viewer);
  await page.setViewportSize({ width: 390, height: 844 });
  await settle(viewer);
  const overflow = await page.evaluate(() => ({
    width: document.documentElement.scrollWidth - window.innerWidth,
    escaped: [...document.querySelectorAll('[data-testid="device-page"] *')].map((element) => ({
      tag: element.tagName, text: element.textContent.slice(0, 100), right: element.getBoundingClientRect().right,
    })).filter((element) => element.right > window.innerWidth + 1).slice(0, 8),
  }));
  expect(overflow.width, JSON.stringify(overflow.escaped)).toBeLessThanOrEqual(1);
  const shot = await viewer.screenshot();
  expect(shot.length).toBeGreaterThan(5000);
  await testInfo.attach('BME280-phone', { body: shot, contentType: 'image/png' });
  await page.getByTestId('device-example').selectOption('esp32_oled_usb');
  await expect(viewer).toHaveAttribute('data-step-count', '12');
  await expect(viewer).toHaveAttribute('data-rendered-modules', JSON.stringify(['mcu', 'display']));
  await expect(page.getByTestId('device-sources').locator('a')).toHaveCount(9);
});
