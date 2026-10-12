const { test, expect } = require('@playwright/test');
const fs = require('node:fs/promises');
const crypto = require('node:crypto');
const APP = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

async function open(page) {
  await page.goto(`${APP}/engineering/device`);
  await expect(page.getByTestId('device-example')).toBeEnabled({ timeout: 40000 });
  await page.getByTestId('device-example').selectOption('esp32_oled_bme280_usb');
  await expect(page.getByTestId('device-modeled-start')).toBeEnabled();
}

test('the real application runs modeled readings and recovery, and its report binds the downloaded source', async ({ page }, info) => {
  await open(page);
  await page.getByTestId('device-modeled-start').click();
  const result = page.getByTestId('device-modeled-result');
  await expect(result).toBeVisible({ timeout: 90000 });
  await expect(result).toHaveAttribute('data-status', /PARTIAL|PASSED/);
  const boot = result.getByTestId('device-modeled-scenario').filter({ hasText: 'boot_ok:' });
  await boot.locator('summary').click();
  await expect(boot.getByTestId('device-modeled-serial')).toContainText('TEMP_C=21.50');
  const recovery = result.getByTestId('device-modeled-scenario').filter({ hasText: 'sensor_missing_at_boot:' });
  await recovery.locator('summary').click();
  await expect(recovery.getByTestId('device-modeled-serial')).toContainText('FAULT_SENSOR_MISSING');
  await expect(recovery.getByTestId('device-modeled-serial')).toContainText('RECOVERED');
  await expect(result).toContainText('ESP32 compilation: NOT_RUN');
  await expect(result).toContainText('Physical correctness: UNPROVEN');
  const reportEvent = page.waitForEvent('download');
  await page.getByTestId('device-modeled-download').click();
  const reportFile = info.outputPath('modeled-run.json');
  await (await reportEvent).saveAs(reportFile);
  const report = JSON.parse(await fs.readFile(reportFile, 'utf8'));
  expect(report.host.scenarios).toHaveLength(15);
  expect(report.firmware_authorized).toBe(false);
  expect(report.power_on_authorized).toBe(false);
  const sourceEvent = page.waitForEvent('download');
  await page.getByTestId('device-application-download').click();
  const sourceFile = info.outputPath('source.zip');
  await (await sourceEvent).saveAs(sourceFile);
  expect(crypto.createHash('sha256').update(await fs.readFile(sourceFile)).digest('hex')).toBe(report.proposal_sha256);
  const spec = JSON.parse(await page.getByTestId('device-spec-editor').inputValue());
  spec.connections.forEach((wire) => { wire.to = wire.to.replace('IO21', 'IO25'); });
  await page.getByTestId('device-spec-editor').fill(JSON.stringify(spec));
  await expect(result).toHaveCount(0);
  await expect(page.getByTestId('device-modeled-start')).toBeDisabled();
});

test('a server refusal does not appear as a completed modeled run', async ({ page }) => {
  await open(page);
  await page.route('**/api/proxy/engineering/devices/application/run', (route) => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ ok: false, error: 'Execution disabled for this test' }),
  }));
  await page.getByTestId('device-modeled-start').click();
  await expect(page.getByTestId('device-modeled-error')).toContainText('Execution disabled');
  await expect(page.getByTestId('device-modeled-result')).toHaveCount(0);
});

test('the proxy refuses malformed and oversized execution requests', async ({ page }) => {
  await open(page);
  const oversized = await page.request.post(`${APP}/api/proxy/engineering/devices/application/run`, { data: 'x'.repeat(65537) });
  expect(oversized.status()).toBe(413);
  const malformed = await page.request.post(`${APP}/api/proxy/engineering/devices/application/run`, { data: { code: 'caller code' } });
  expect((await malformed.json()).ok).toBe(false);
});

test('a late modeled response cannot attach itself to newly checked wiring', async ({ page }) => {
  await open(page);
  let release;
  let ready;
  const held = new Promise((resolve) => { release = resolve; });
  const received = new Promise((resolve) => { ready = resolve; });
  await page.route('**/api/proxy/engineering/devices/application/run', async (route) => {
    const response = await route.fetch();
    ready();
    await held;
    await route.fulfill({ response }).catch(() => {}); // the UI intentionally aborts this request
  });
  await page.getByTestId('device-modeled-start').click();
  await received;
  const spec = JSON.parse(await page.getByTestId('device-spec-editor').inputValue());
  spec.name = 'A newly checked build';
  await page.getByTestId('device-spec-editor').fill(JSON.stringify(spec));
  await page.getByTestId('device-spec-apply').click();
  await expect(page.getByTestId('device-modeled-start')).toBeEnabled();
  release();
  await page.waitForTimeout(500);
  await expect(page.getByTestId('device-modeled-result')).toHaveCount(0);
});

test('a BH1750 build runs the same modeled tests and says its adapter has no bus model', async ({ page }, info) => {
  await open(page);
  const spec = JSON.parse(await page.getByTestId('device-spec-editor').inputValue());
  spec.modules.find((module) => module.id === 'sensor').module = 'adafruit-bh1750-stemma-qt';
  const rename = { 'sensor.Vin': 'sensor.VIN', 'sensor.SCK': 'sensor.SCL', 'sensor.SDI': 'sensor.SDA' };
  spec.connections = spec.connections.map((wire) => ({
    from: Object.entries(rename).reduce((value, [from, to]) => value.replace(from, to), wire.from),
    to: Object.entries(rename).reduce((value, [from, to]) => value.replace(from, to), wire.to),
  }));
  await page.getByTestId('device-spec-editor').fill(JSON.stringify(spec));
  await page.getByTestId('device-spec-apply').click();
  await expect(page.getByTestId('device-modeled-start')).toBeEnabled({ timeout: 40000 });
  await page.getByTestId('device-modeled-start').click();
  const result = page.getByTestId('device-modeled-result');
  await expect(result).toBeVisible({ timeout: 90000 });
  await expect(result).toHaveAttribute('data-status', 'PARTIAL');
  await expect(result).toContainText('No vendor-host lane exists for the BH1750');
  await expect(result).toContainText('Core logic: PASSED (15/15 scenarios)');
  const boot = result.getByTestId('device-modeled-scenario').filter({ hasText: 'boot_ok:' });
  await boot.locator('summary').click();
  await expect(boot.getByTestId('device-modeled-serial')).toContainText('LUX=320.0');
  const reportEvent = page.waitForEvent('download');
  await page.getByTestId('device-modeled-download').click();
  const reportFile = info.outputPath('modeled-run-bh1750.json');
  await (await reportEvent).saveAs(reportFile);
  const report = JSON.parse(await fs.readFile(reportFile, 'utf8'));
  expect(report.host.scenarios).toHaveLength(15);
  expect(report.vendor_host.status).toBe('NOT_RUN');
  expect(report.firmware_authorized).toBe(false);
  expect(report.power_on_authorized).toBe(false);
  expect(report.physical_correctness).toBe('UNPROVEN');
  const sourceEvent = page.waitForEvent('download');
  await page.getByTestId('device-application-download').click();
  const sourceFile = info.outputPath('source-bh1750.zip');
  await (await sourceEvent).saveAs(sourceFile);
  expect(crypto.createHash('sha256').update(await fs.readFile(sourceFile)).digest('hex')).toBe(report.proposal_sha256);
});
