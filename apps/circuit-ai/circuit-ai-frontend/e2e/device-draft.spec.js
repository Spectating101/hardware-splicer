const { test, expect } = require('@playwright/test');

const APP = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

async function open(page) {
  await page.goto(`${APP}/engineering/device`);
  await expect(page.getByTestId('device-firmware-download')).toBeEnabled({ timeout: 40000 });
}

test('a typed parts list drafts the wiring, loads it, and says what each line was read as', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await open(page);
  await page.getByTestId('device-parts-text').fill('Raspberry Pi Pico, BH1750, 0.96 inch OLED\nHC-SR04 ultrasonic');
  await page.getByTestId('device-parts-draft').click();
  const panel = page.getByTestId('device-draft');
  await expect(panel).toBeVisible();
  const lines = panel.getByTestId('device-draft-line');
  await expect(lines).toHaveCount(4);
  await expect(lines.nth(0)).toHaveAttribute('data-status', 'matched');
  await expect(lines.nth(0)).toContainText('Raspberry Pi Pico (RP2040)');
  await expect(lines.nth(1)).toHaveAttribute('data-status', 'matched');
  await expect(lines.nth(1)).toContainText('chip name');
  // "OLED" is a generic word: matched, but the person is asked to check it.
  await expect(lines.nth(2)).toHaveAttribute('data-status', 'generic');
  await expect(lines.nth(2)).toContainText('check this is your part');
  await expect(lines.nth(3)).toHaveAttribute('data-status', 'left_out');
  await expect(lines.nth(3)).toContainText('Not in the device library');
  await expect(panel).toContainText('approves nothing');
  // The draft is the spec now: planned, editable, and the example picker says so.
  const spec = JSON.parse(await page.getByTestId('device-spec-editor').inputValue());
  expect(spec.modules.map((m) => m.module)).toEqual(['raspberry-pi-pico', 'adafruit-bh1750-stemma-qt', 'ssd1306-096-i2c']);
  await expect(page.getByTestId('device-example')).toHaveValue('');
  await expect(page.getByTestId('device-example').locator('option:checked')).toHaveText('Your parts list');
  await expect(page.getByTestId('device-firmware-download')).toBeEnabled();
  expect(errors).toEqual([]);
});

test('a list naming a different board is refused with a reason and the current plan is kept', async ({ page }) => {
  await open(page);
  const before = await page.getByTestId('device-spec-editor').inputValue();
  await page.getByTestId('device-parts-text').fill('ESP32-S3 devkit, BME280');
  await page.getByTestId('device-parts-draft').click();
  await expect(page.getByTestId('device-parts-error')).toContainText('controller');
  await expect(page.getByTestId('device-draft')).toHaveCount(0);
  expect(await page.getByTestId('device-spec-editor').inputValue()).toBe(before);
  await expect(page.getByTestId('device-firmware-download')).toBeEnabled();
});

test('the draft proxy refuses oversized bodies without reaching the backend', async ({ page }) => {
  const tooLarge = await page.request.post(`${APP}/api/proxy/engineering/devices/draft`, { data: 'x'.repeat(16 * 1024 + 1) });
  expect(tooLarge.status()).toBe(413);
  expect((await tooLarge.json()).ok).toBe(false);
});
