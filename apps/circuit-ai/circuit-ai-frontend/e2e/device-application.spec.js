const { test, expect } = require('@playwright/test');
const { execFileSync, spawnSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');

const APP = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const python = path.resolve(__dirname, '../../../../.venv/bin/python');
const sha = (data) => crypto.createHash('sha256').update(data).digest('hex');

async function open(page, example) {
  await page.goto(`${APP}/engineering/device`);
  await expect(page.getByTestId('device-application-download')).toBeEnabled({ timeout: 40000 });
  await page.getByTestId('device-example').selectOption(example);
  await expect(page.getByTestId('device-viewer')).not.toHaveAttribute('data-step-count', '');
}

test('the real application download is bound to the wiring, runs its own host tests and claims nothing physical', async ({ page }, info) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await open(page, 'esp32_oled_bme280_usb');
  await expect(page.getByTestId('device-viewer')).toHaveAttribute('data-step-count', '17');
  await expect(page.getByTestId('device-application')).toContainText('do not cover the Adafruit libraries');
  const waiting = page.waitForEvent('download');
  await page.getByTestId('device-application-download').click();
  const download = await waiting;
  expect(download.suggestedFilename()).toBe('device-application-proposal.zip');
  const file = info.outputPath('device-application-proposal.zip');
  await download.saveAs(file);
  const dir = info.outputPath('application');
  fs.mkdirSync(dir, { recursive: true });
  const names = JSON.parse(execFileSync(python, ['-c', 'import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; z.extractall(sys.argv[2]); print(json.dumps(z.namelist()))', file, dir], { encoding: 'utf8' }));
  expect(names).toEqual(expect.arrayContaining(['src/app_core.h', 'src/main.cpp', 'platformio.ini', 'test/host/harness.cpp', 'FIRMWARE_PROPOSAL.json']));
  const meta = JSON.parse(fs.readFileSync(path.join(dir, 'FIRMWARE_PROPOSAL.json'), 'utf8'));
  expect(meta.schema_version).toBe('hardware_splicer.device_application_proposal.v1');
  expect(meta.pins.sda.gpio).toBe(21);
  expect(meta.pins.scl.gpio).toBe(22);
  expect(meta.compilation).toBe('NOT_RUN');
  expect(meta.behaviour_tests).toBe('NOT_RUN');
  expect(meta.firmware_authorized).toBe(false);
  expect(meta.power_on_authorized).toBe(false);
  expect(meta.physical_correctness).toBe('UNPROVEN');
  for (const [name, facts] of Object.entries(meta.files)) expect(sha(fs.readFileSync(path.join(dir, name)))).toBe(facts.sha256);
  const main = fs.readFileSync(path.join(dir, 'src/main.cpp'), 'utf8');
  expect(main).toContain('constexpr int SDA_PIN = 21;');
  expect(main).toContain('constexpr int SCL_PIN = 22;');
  // The package's own instructions: build and run the host tests exactly as the README says.
  const build = spawnSync('g++', ['-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', 'src', 'test/host/harness.cpp', '-o', 'harness'], { cwd: dir, encoding: 'utf8' });
  test.skip(build.error && build.error.code === 'ENOENT', 'g++ is not installed');
  expect(build.status, build.stderr).toBe(0);
  const run = spawnSync('./harness', [], { cwd: dir, encoding: 'utf8' });
  expect(run.status, run.stdout).toBe(0);
  const rows = run.stdout.trim().split('\n').map((line) => JSON.parse(line));
  expect(rows.length).toBeGreaterThanOrEqual(15);
  expect(rows.filter((row) => !row.pass)).toEqual([]);
  await expect(page.getByTestId('device-application-message')).toContainText('host tests and compilation have not run here');
  expect(errors).toEqual([]);
});

test('an unsupported device says why instead of downloading, and a GPIO change reaches the source', async ({ page }, info) => {
  await open(page, 'esp32_oled_usb');
  await page.getByTestId('device-application-download').click();
  await expect(page.getByTestId('device-application-message')).toContainText('BME280');
  await page.getByTestId('device-example').selectOption('esp32_oled_bme280_usb');
  await expect(page.getByTestId('device-viewer')).toHaveAttribute('data-step-count', '17');
  const spec = JSON.parse(await page.getByTestId('device-spec-editor').inputValue());
  for (const wire of spec.connections) wire.to = wire.to.replace('IO21', 'IO25').replace('IO22', 'IO26');
  await page.getByTestId('device-spec-editor').fill(JSON.stringify(spec));
  await expect(page.getByTestId('device-application-download')).toBeDisabled();
  await page.getByTestId('device-spec-apply').click();
  await expect(page.getByTestId('device-application-download')).toBeEnabled();
  const waiting = page.waitForEvent('download');
  await page.getByTestId('device-application-download').click();
  const file = info.outputPath('custom-gpio-application.zip');
  await (await waiting).saveAs(file);
  const main = execFileSync(python, ['-c', 'import sys,zipfile; print(zipfile.ZipFile(sys.argv[1]).read("src/main.cpp").decode())', file], { encoding: 'utf8' });
  expect(main).toContain('constexpr int SDA_PIN = 25;');
  expect(main).toContain('constexpr int SCL_PIN = 26;');
  expect(main).not.toContain('constexpr int SDA_PIN = 21;');
});

test('the Pico example downloads a Pico package on its own I2C pins, with the same host tests and an RP2040 vendor-host lane', async ({ page }, info) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await open(page, 'pico_oled_bme280_usb');
  await expect(page.getByTestId('device-application-download')).toBeEnabled();
  await expect(page.getByTestId('device-application')).toContainText('Raspberry Pi Pico');
  const waiting = page.waitForEvent('download');
  await page.getByTestId('device-application-download').click();
  const file = info.outputPath('pico-application.zip');
  await (await waiting).saveAs(file);
  const dir = info.outputPath('pico');
  fs.mkdirSync(dir, { recursive: true });
  const names = JSON.parse(execFileSync(python, ['-c', 'import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; z.extractall(sys.argv[2]); print(json.dumps(z.namelist()))', file, dir], { encoding: 'utf8' }));
  expect(names).toEqual(expect.arrayContaining(['test/vendor_host/Wire.h', 'test/vendor_host/board_config.h', 'test/vendor_host/wire_pins_rp2040.h']));
  const meta = JSON.parse(fs.readFileSync(path.join(dir, 'FIRMWARE_PROPOSAL.json'), 'utf8'));
  expect(meta.target.board).toBe('pico');
  expect([meta.pins.sda.printed_name, meta.pins.scl.printed_name]).toEqual(['GP4', 'GP5']);
  expect(meta.firmware_authorized).toBe(false);
  expect(meta.physical_correctness).toBe('UNPROVEN');
  expect(meta.vendor_host_claim_boundary).toContain('RP2040 Wire driver');
  expect(fs.readFileSync(path.join(dir, 'test/vendor_host/Wire.h'), 'utf8')).toContain('arduino-pico TwoWire');
  expect(fs.readFileSync(path.join(dir, 'test/vendor_host/board_config.h'), 'utf8')).toContain('#define HS_WIRE Wire\n');
  expect(fs.readFileSync(path.join(dir, 'platformio.ini'), 'utf8')).toContain('board_build.core = earlephilhower');
  const main = fs.readFileSync(path.join(dir, 'src/main.cpp'), 'utf8');
  expect(main).toContain('Wire.setSDA(SDA_PIN)');
  expect(main).not.toContain('Wire.begin(SDA_PIN, SCL_PIN, 100000)');
  const build = spawnSync('g++', ['-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', 'src', 'test/host/harness.cpp', '-o', 'harness'], { cwd: dir, encoding: 'utf8' });
  test.skip(build.error && build.error.code === 'ENOENT', 'g++ is not installed');
  expect(build.status, build.stderr).toBe(0);
  const run = spawnSync('./harness', [], { cwd: dir, encoding: 'utf8' });
  expect(run.status, run.stdout).toBe(0);
  expect(errors).toEqual([]);
});
