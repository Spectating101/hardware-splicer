const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';
const DONOR = `${APP_URL}/engineering/donor`;
const BANNED = /\b(identified|verified|compatible|ready|safe|passed)\b/i;

async function planWith(page, marking) {
  await page.setViewportSize({ width: 1500, height: 1000 });
  await page.addInitScript(() => { try { if (!sessionStorage.getItem('__seeded')) { localStorage.clear(); sessionStorage.setItem('__seeded', '1'); } } catch { /* ignore */ } });
  await page.goto(DONOR);
  await expect(page.getByTestId('donor-kind').locator('option')).not.toHaveCount(0, { timeout: 20000 });
  await page.getByTestId('donor-add-centre').click();
  await page.getByTestId('donor-marking').fill(marking);
  await page.getByTestId('donor-plan').click();
  await expect(page.getByTestId('reclaim-table')).toBeVisible({ timeout: 30000 });
}

test('a chip the device library lists on a module is offered with the caveat that the chip alone is not that module', async ({ page }) => {
  await planWith(page, 'SSD1306');
  const link = page.getByTestId('reclaim-device-match');
  await expect(link).toHaveCount(1, { timeout: 15000 });
  await expect(link).toHaveAttribute('data-relation', 'chip_on_module');
  await expect(link).toContainText('display controller on the module');
  await expect(link).toContainText('not that module');
  await expect(link).toContainText('not proof');
  expect((await link.textContent()) || '').not.toMatch(BANNED);

  await link.click();
  await expect(page).toHaveURL(/\/engineering\/device\?from=donor/);
  const onHand = page.getByTestId('device-on-hand');
  await expect(onHand).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId('device-on-hand-part')).toHaveCount(1);
  await expect(onHand).toContainText('marking you read: SSD1306');
  await expect(onHand).toContainText('not that module');
  await expect(onHand.locator('[data-relation="chip_on_module"] a')).toHaveAttribute('href', 'https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf');
  expect((await onHand.textContent()) || '').not.toMatch(BANNED);
});

test('a different module or a shorter start of the listed part is not offered', async ({ page }) => {
  await planWith(page, 'ESP32-WROOM-32');            // a different module from the listed ESP32-WROOM-32E
  await page.waitForTimeout(1500);
  await expect(page.getByTestId('reclaim-device-match')).toHaveCount(0);
});

test('the listed radio module and a grade variant of it are offered, as the same name and as a variant', async ({ page }) => {
  await planWith(page, 'ESP32-WROOM-32E-N4');
  const link = page.getByTestId('reclaim-device-match');
  await expect(link).toHaveCount(1, { timeout: 15000 });
  await expect(link).toContainText('variant');
  await expect(link).toContainText('Wi-Fi/Bluetooth module on the board');
});

test('the device page without a handoff shows no on-hand list', async ({ page }) => {
  await page.goto(`${APP_URL}/engineering/device`);
  await expect(page.getByTestId('device-on-hand')).toHaveCount(0);
});
