const { test, expect } = require('@playwright/test');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const APP = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const python = path.resolve(__dirname, '../../../../.venv/bin/python');

test('the case download is bound to the planned case, closed, and claims nothing physical', async ({ page }, info) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(`${APP}/engineering/device`);
  await expect(page.getByTestId('device-case-download')).toBeEnabled({ timeout: 40000 });
  await page.getByTestId('device-example').selectOption('esp32_oled_bme280_usb');
  await expect(page.getByTestId('device-viewer')).not.toHaveAttribute('data-step-count', '');
  await expect(page.getByTestId('device-case')).toContainText('Not printed or test-fitted');
  const waiting = page.waitForEvent('download');
  await page.getByTestId('device-case-download').click();
  const download = await waiting;
  expect(download.suggestedFilename()).toBe('device-case-proposal.zip');
  const file = info.outputPath('device-case-proposal.zip');
  await download.saveAs(file);
  const dir = info.outputPath('case');
  fs.mkdirSync(dir, { recursive: true });
  const names = JSON.parse(execFileSync(python, ['-c', 'import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; z.extractall(sys.argv[2]); print(json.dumps(z.namelist()))', file, dir], { encoding: 'utf8' }));
  expect(names).toEqual(expect.arrayContaining(['case_base.stl', 'case_lid.stl', 'case_base.scad', 'case_lid.scad', 'CASE_PROPOSAL.json']));
  const meta = JSON.parse(fs.readFileSync(path.join(dir, 'CASE_PROPOSAL.json'), 'utf8'));
  expect(meta.schema_version).toBe('hardware_splicer.device_case_proposal.v1');
  expect(meta.meshes.case_base.closed_manifold).toBe(true);
  expect(meta.meshes.case_lid.closed_manifold).toBe(true);
  expect(meta.printed).toBe(false);
  expect(meta.test_fitted).toBe(false);
  expect(meta.physical_correctness).toBe('UNPROVEN');
  expect(meta.firmware_authorized).toBe(false);
  expect(meta.power_on_authorized).toBe(false);
  await expect(page.getByTestId('device-case-message')).toContainText('not been printed or test-fitted');
  expect(errors).toEqual([]);
});
