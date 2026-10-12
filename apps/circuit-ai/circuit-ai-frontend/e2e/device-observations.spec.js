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
