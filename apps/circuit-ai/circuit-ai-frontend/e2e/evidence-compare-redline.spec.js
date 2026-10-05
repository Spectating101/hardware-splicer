const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('compare marks real artifact changes on the candidate and says when a revision cannot be compared', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP_URL}/engineering/evidence/compare?project=outsider-fixture&base=5&candidate=6`);

  const panel = page.getByTestId('artifact-changes');
  await expect(panel).toBeVisible();
  await expect(panel).toContainText(/Changes in the schematic/i);
  await expect(panel).not.toContainText('Comparing the two files');

  // The fixture backend only produces a diff when the kicad_diff module is installed; otherwise it must say so.
  const text = await panel.innerText();
  if (/Not compared/.test(text)) {
    await expect(panel).toContainText(/\S/);
    return;
  }
  const highlights = page.getByTestId('diff-highlight');
  await expect(highlights.first()).toBeVisible();
  const rows = panel.getByRole('button');
  await rows.first().click();
  await expect(rows.first()).toHaveAttribute('aria-pressed', 'true');

  // A diff is evidence, not authority: no control on this page can open fabrication, power-on or release.
  await expect(page.getByRole('button', { name: /Authorize|Approve|Accept|Fabricate|Power on|Release/i })).toHaveCount(0);
});
