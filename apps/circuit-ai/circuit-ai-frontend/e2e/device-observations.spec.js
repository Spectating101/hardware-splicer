const { test, expect } = require('@playwright/test');

const APP = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

const HEADER = 'Declared possible addresses, NOT observations: 0x3C 0x3D 0x76 0x77';
const ack = (address) => `Observed ACK at 0x${address}; identity and function unverified.`;
const total = (n) => `Observed acknowledgements: ${n}. No sensor readings or physical validation.`;

async function open(page) {
  await page.goto(`${APP}/engineering/device`);
  await expect(page.getByTestId('device-firmware-download')).toBeEnabled({ timeout: 40000 });
  await page.getByTestId('device-example').selectOption('esp32_oled_bme280_usb');
  await expect(page.getByTestId('device-viewer')).toHaveAttribute('data-step-count', '17');
}

async function compare(page, text) {
  await page.getByTestId('device-scan-input').fill(text);
  await page.getByTestId('device-scan-check').click();
}

test('a scan where each module answers is compared and still claims nothing', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await open(page);
  await expect(page.getByTestId('device-scan-check')).toBeDisabled();
  await compare(page, [HEADER, ack('3C'), ack('77'), total(2)].join('\n'));
  const modules = page.getByTestId('device-scan-module');
  await expect(modules).toHaveCount(2);
  await expect(modules.nth(0)).toHaveAttribute('data-status', 'acknowledged');
  await expect(modules.nth(1)).toHaveAttribute('data-status', 'acknowledged');
  await expect(page.getByTestId('device-scan-result')).toContainText('Declared 0x3C or 0x3D; answered at 0x3C');
  await expect(page.getByTestId('device-scan-boundary')).toContainText('does not identify the chip');
  await expect(page.getByTestId('device-scan-boundary')).toContainText('cannot tell whether it came from the planned hardware');
  const text = await page.getByTestId('device-scan').innerText();
  expect(text).not.toMatch(/\b(verified|approved|passed|works|safe to)\b/i);
  expect(errors).toEqual([]);
});

test('a missing answer is reported without guessing why', async ({ page }) => {
  await open(page);
  await compare(page, [HEADER, ack('3C'), total(1)].join('\n'));
  const sensor = page.getByTestId('device-scan-module').filter({ hasText: 'BME280' });
  await expect(sensor).toHaveAttribute('data-status', 'no_acknowledge');
  await expect(sensor).toContainText('cannot say why');
});

test('a cut-off scan is not assessed and an unlisted address is mentioned neutrally', async ({ page }) => {
  await open(page);
  await compare(page, [ack('3C'), ack('77')].join('\n'));
  for (const status of await page.getByTestId('device-scan-module').evaluateAll((nodes) => nodes.map((n) => n.getAttribute('data-status')))) {
    expect(status).toBe('not_assessed');
  }
  await expect(page.getByTestId('device-scan-result')).toContainText('may be cut short');
  await compare(page, [ack('3C'), ack('77'), ack('57'), total(3)].join('\n'));
  await expect(page.getByTestId('device-scan-unexpected')).toContainText('0x57');
  await expect(page.getByTestId('device-scan-unexpected')).toContainText('cannot say what it is');
});

test('text with control characters is refused and a new wiring check clears the old result', async ({ page }) => {
  await open(page);
  await compare(page, 'x\u001b[31mred');
  await expect(page.getByTestId('device-scan-error')).toContainText('control characters');
  await compare(page, [ack('3C'), ack('77'), total(2)].join('\n'));
  await expect(page.getByTestId('device-scan-result')).toBeVisible();
  await page.getByTestId('device-spec-apply').click();
  await expect(page.getByTestId('device-scan-result')).toHaveCount(0);
});

test('the application\'s own boot line is read, with what it does and does not establish', async ({ page }) => {
  await open(page);
  await compare(page, ['BOOT sensor=0x77 display=0x3C', 'T=0 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3'].join('\n'));
  const modules = page.getByTestId('device-scan-module');
  await expect(modules).toHaveCount(2);
  await expect(modules.filter({ hasText: 'BME280' })).toHaveAttribute('data-status', 'acknowledged');
  await expect(modules.filter({ hasText: 'BME280' })).toContainText("application's own chip-id check");
  await expect(modules.filter({ hasText: 'SSD1306' })).toContainText("not a display identity");
  await expect(page.getByTestId('device-scan-boundary')).toContainText('cannot tell whether it came from the planned hardware');
  await compare(page, 'DISPLAY MISSING\nBOOT sensor=0x76 display=NONE');
  await expect(page.getByTestId('device-scan-module').filter({ hasText: 'SSD1306' })).toHaveAttribute('data-status', 'no_acknowledge');
});

test('later faults and stale readings do not inherit an earlier boot success', async ({ page }) => {
  await open(page);
  const sensor = page.getByTestId('device-scan-module').filter({ hasText: 'BME280' });
  for (const [state, status] of [['FAULT_AMBIGUOUS_ADDRESS', 'ambiguous'], ['FAULT_SENSOR_READ', 'sensor_read_fault'], ['STALE', 'stale']]) {
    await compare(page, `BOOT sensor=0x77 display=0x3C\nT=2000 STATE=${state}`);
    await expect(sensor).toHaveAttribute('data-status', status);
    await expect(sensor).toContainText('earlier boot');
  }
  await compare(page, 'BOOT sensor=0x77 display=0x3C\nT=2000 STATE=FAULT_SENSOR_READ\nRECOVERED\nT=4000 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3');
  await expect(sensor).toHaveAttribute('data-status', 'acknowledged');
});
