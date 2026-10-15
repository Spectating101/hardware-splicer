const { test, expect } = require('@playwright/test');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');

const APP = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const python = path.resolve(__dirname, '../../../../.venv/bin/python');
const sha = (data) => crypto.createHash('sha256').update(data).digest('hex');

async function open(page) {
  await page.goto(`${APP}/engineering/device`);
  await expect(page.getByTestId('device-firmware-download')).toBeEnabled({ timeout: 40000 });
  await page.getByTestId('device-example').selectOption('esp32_oled_bme280_usb');
  await expect(page.getByTestId('device-viewer')).toHaveAttribute('data-step-count', '17');
  await expect(page.getByTestId('device-firmware-download')).toBeEnabled();
  return JSON.parse(await page.getByTestId('device-spec-editor').inputValue());
}

test('the real download binds the sensor plan, GPIOs and source without claiming compilation', async ({ page }, info) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const spec = await open(page);
  const waiting = page.waitForEvent('download');
  await page.getByTestId('device-firmware-download').click();
  const download = await waiting;
  expect(download.suggestedFilename()).toBe('device-diagnostic-proposal.zip');
  const file = info.outputPath('device-diagnostic-proposal.zip');
  await download.saveAs(file);
  const zip = JSON.parse(execFileSync(python, ['-c', 'import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; print(json.dumps({n:z.read(n).decode() for n in z.namelist()}))', file], { encoding: 'utf8' }));
  const meta = JSON.parse(zip['FIRMWARE_PROPOSAL.json']);
  expect(meta.pins.sda.gpio).toBe(21);
  expect(meta.pins.scl.gpio).toBe(22);
  expect(meta.declared_devices.map((d) => d.module)).toEqual(['display', 'sensor']);
  expect(meta.compilation).toBe('NOT_RUN');
  expect(meta.firmware_authorized).toBe(false);
  expect(meta.power_on_authorized).toBe(false);
  expect(meta.observations).toEqual([]);
  expect(JSON.parse(zip['DEVICE_SPEC.json'])).toEqual(spec);
  for (const [name, facts] of Object.entries(meta.files)) expect(sha(zip[name])).toBe(facts.sha256);
  expect(zip['src/main.cpp']).toContain('Serial.read()');
  expect(zip['src/main.cpp']).toContain('Wire.begin(SDA_PIN, SCL_PIN, BUS_HZ)');
  const again = await page.request.post(`${APP}/api/proxy/engineering/devices/firmware`, { data: spec });
  expect(again.headers()['content-type']).toBe('application/zip');
  expect(sha(await again.body())).toBe(sha(fs.readFileSync(file)));
  await expect(page.getByTestId('device-firmware-message')).toContainText('Compilation has not run');
  expect(errors).toEqual([]);
});

test('editing GPIOs closes download until checked and the new package uses those GPIOs', async ({ page }, info) => {
  const spec = await open(page);
  for (const wire of spec.connections) wire.to = wire.to.replace('IO21', 'IO25').replace('IO22', 'IO26');
  await page.getByTestId('device-spec-editor').fill(JSON.stringify(spec));
  await expect(page.getByTestId('device-firmware-download')).toBeDisabled();
  await expect(page.getByTestId('device-firmware')).toContainText('Check the edited wiring');
  await page.getByTestId('device-spec-apply').click();
  await expect(page.getByTestId('device-firmware-download')).toBeEnabled();
  const waiting = page.waitForEvent('download');
  await page.getByTestId('device-firmware-download').click();
  const file = info.outputPath('custom-gpio-proposal.zip');
  await (await waiting).saveAs(file);
  const source = execFileSync(python, ['-c', 'import sys,zipfile; print(zipfile.ZipFile(sys.argv[1]).read("src/main.cpp").decode())', file], { encoding: 'utf8' });
  expect(source).toContain('SDA_PIN = 25;');
  expect(source).toContain('SCL_PIN = 26;');
});

test('wrong wiring blocks both the UI and a direct proxy export with forged findings', async ({ page }) => {
  const spec = await open(page);
  spec.connections[7].to = 'mcu.D2';
  await page.getByTestId('device-spec-editor').fill(JSON.stringify(spec));
  await page.getByTestId('device-spec-apply').click();
  await expect(page.locator('[data-rule="flash_pin"]')).toBeVisible();
  await expect(page.getByTestId('device-firmware-download')).toBeDisabled();
  const response = await page.request.post(`${APP}/api/proxy/engineering/devices/firmware`, { data: { spec, plan: { findings: [], firmware_authorized: true } } });
  const body = await response.json();
  expect(body.ok).toBe(false);
  expect(body.status).toBe(422);
  expect(body.error).toContain('flash_pin');
});

test('the Pico example downloads a Pico diagnostic that starts its own controller the arduino-pico way', async ({ page }, info) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await open(page);
  await page.getByTestId('device-example').selectOption('pico_oled_bme280_usb');
  await expect(page.getByTestId('device-spec-editor')).toHaveValue(/raspberry-pi-pico/);
  await expect(page.getByTestId('device-firmware-download')).toBeEnabled();
  const waiting = page.waitForEvent('download');
  await page.getByTestId('device-firmware-download').click();
  const file = info.outputPath('pico-diagnostic.zip');
  await (await waiting).saveAs(file);
  const zip = JSON.parse(execFileSync(python, ['-c', 'import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; print(json.dumps({n:z.read(n).decode() for n in z.namelist()}))', file], { encoding: 'utf8' }));
  const meta = JSON.parse(zip['FIRMWARE_PROPOSAL.json']);
  expect(meta.target.board).toBe('pico');
  expect([meta.pins.sda.printed_name, meta.pins.scl.printed_name]).toEqual(['GP4', 'GP5']);
  expect(meta.compilation).toBe('NOT_RUN');
  expect(meta.firmware_authorized).toBe(false);
  expect(meta.power_on_authorized).toBe(false);
  expect(meta.physical_correctness).toBe('UNPROVEN');
  expect(zip['platformio.ini']).toContain('board_build.core = earlephilhower');
  expect(zip['src/main.cpp']).toContain('Wire.setSDA(SDA_PIN)');
  expect(zip['src/main.cpp']).not.toContain('Wire.begin(SDA_PIN');
  await expect(page.getByTestId('device-firmware-message')).toContainText('Compilation has not run');
  expect(errors).toEqual([]);
});

test('an upstream refusal never becomes a successful download message', async ({ page }) => {
  await open(page);
  await page.route('**/api/proxy/engineering/devices/firmware', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ ok: false, error: 'Resolve wiring checks: fixture refusal', status: 422 }),
  }));
  await page.getByTestId('device-firmware-download').click();
  await expect(page.getByTestId('device-firmware-message')).toContainText('fixture refusal');
  await expect(page.getByTestId('device-firmware-message')).not.toContainText('Source downloaded');
});

test('the export proxy refuses oversized and malformed bodies without a ZIP', async ({ page }) => {
  const tooLarge = await page.request.post(`${APP}/api/proxy/engineering/devices/firmware`, { data: 'x'.repeat(65537) });
  expect(tooLarge.status()).toBe(413);
  const bad = await page.request.post(`${APP}/api/proxy/engineering/devices/firmware`, { data: 'not JSON', headers: { 'content-type': 'application/json' } });
  expect((await bad.json()).ok).toBe(false);
  expect(bad.headers()['content-type']).not.toContain('application/zip');
});
