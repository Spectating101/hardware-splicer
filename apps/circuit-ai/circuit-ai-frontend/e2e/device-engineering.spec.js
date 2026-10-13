const { test, expect } = require('@playwright/test');
const fs = require('node:fs/promises');

const APP = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('the engineering review is computed from the layout, shows sourced and assumed numbers, and never says a design works', async ({ page }, info) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(`${APP}/engineering/device`);
  await expect(page.getByTestId('device-engineering-start')).toBeEnabled({ timeout: 40000 });
  await page.getByTestId('device-example').selectOption('esp32_oled_bme280_usb');
  await expect(page.getByTestId('device-viewer')).not.toHaveAttribute('data-step-count', '');
  await expect(page.getByTestId('device-engineering-start')).toBeEnabled({ timeout: 40000 });
  await page.getByTestId('device-engineering-start').click();
  const result = page.getByTestId('device-engineering-result');
  await expect(result).toBeVisible({ timeout: 30000 });
  await expect(result).toContainText('Physical correctness: UNPROVEN');
  const antenna = result.locator('[data-check="antenna_clearance"]');
  await expect(antenna).toHaveAttribute('data-status', 'exceeds_limit');
  await expect(antenna).toContainText('at least 15 mm');
  await expect(antenna.locator('a')).toHaveAttribute('href', /esp-hardware-design-guidelines/);
  await expect(result.locator('[data-check="i2c_bus"]')).toHaveAttribute('data-status', 'not_assessed');
  await expect(result.locator('[data-check="temperature_bias_sensor"]')).toHaveAttribute('data-status', 'advisory');
  await expect(page.getByTestId('device-engineering-not-assessed')).toContainText('EMC and radio regulation');
  const statuses = await result.getByTestId('device-engineering-check').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-status')));
  expect(statuses.every((status) => ['exceeds_limit', 'advisory', 'within_limit_under_assumptions', 'not_assessed'].includes(status))).toBe(true);
  const reportEvent = page.waitForEvent('download');
  await page.getByTestId('device-engineering-download').click();
  const file = info.outputPath('device-engineering-review.json');
  await (await reportEvent).saveAs(file);
  const report = JSON.parse(await fs.readFile(file, 'utf8'));
  expect(report.schema_version).toBe('hardware_splicer.device_engineering_review.v1');
  expect(report.firmware_authorized).toBe(false);
  expect(report.power_on_authorized).toBe(false);
  expect(errors).toEqual([]);
});
