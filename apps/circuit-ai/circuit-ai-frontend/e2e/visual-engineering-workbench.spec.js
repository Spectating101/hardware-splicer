const { test, expect } = require('@playwright/test');

const APP_URL = process.env.OUTSIDER_APP_URL || 'http://127.0.0.1:3000';

test('task-adaptive workbench preserves canonical evidence, blockers, and deep-linked state', async ({ page }) => {
  await page.goto(`${APP_URL}/engineering/visual`);

  await expect(page.getByRole('heading', { name: 'Visual Engineering Workbench' })).toBeVisible();
  await expect(page.getByText('Hardware Splicer moat layer')).toBeVisible();
  await expect(page.getByText('Viewers grant no authority')).toBeVisible();
  await expect(page.getByText('Revision 6', { exact: true }).first()).toBeVisible();

  await expect(page.getByRole('button', { name: /Explore/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Decide/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Verify/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Bring-up/ })).toBeVisible();

  await expect(page.getByText('USB fixture controller', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Unresolved translation', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('32-pin DUT socket', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Current-limited 1.8 V rail', { exact: true }).first()).toBeVisible();

  await page.getByText('Unresolved translation', { exact: true }).first().click();
  await expect(page.getByText('Contextual JARVIS inspector')).toBeVisible();
  await expect(page.getByText('dut-datasheet-r1', { exact: true })).toBeVisible();
  await expect(page.getByText('fixture-controller-manual-r1', { exact: true })).toBeVisible();
  await expect(page.getByText(/1.8 V DUT interface is not protected from 3.3 V controller/)).toBeVisible();
  await expect(page.getByText('Selected canonical ID:')).toBeVisible();
  await expect(page.getByText('level-translation', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/object=level-translation/);

  await page.getByRole('button', { name: /Decide/ }).click();
  await expect(page.getByRole('heading', { name: 'Current state versus proposed successor' })).toBeVisible();
  await expect(page.getByText('Semantic change summary')).toBeVisible();
  await expect(page.getByText('This visual workbench remains read-only.')).toBeVisible();
  await expect(page).toHaveURL(/mode=decide/);
  await expect(page).toHaveURL(/object=level-translation/);

  await page.getByRole('button', { name: /Verify/ }).click();
  await expect(page.getByRole('heading', { name: 'Checks, failures, and repair eligibility' })).toBeVisible();
  await expect(page.getByText('Selected-object verification ladder')).toBeVisible();
  await expect(page.getByText(/persisted failure/)).toBeVisible();
  await expect(page).toHaveURL(/mode=verify/);

  await page.getByRole('button', { name: /Bring-up/ }).click();
  await expect(page.getByRole('heading', { name: 'Procedure readiness and missing physical evidence' })).toBeVisible();
  await expect(page.getByText('All physical gates closed')).toBeVisible();
  await expect(page.getByText('Physical measurement captured')).toBeVisible();
  await expect(page.getByText(/No measurement capture contract is implemented/)).toBeVisible();
  await expect(page).toHaveURL(/mode=bringup/);

  await page.getByRole('button', { name: /Explore/ }).click();
  await expect(page.getByText('Unresolved translation', { exact: true }).first()).toBeVisible();
  await expect(page).toHaveURL(/mode=explore/);

  const objectSearch = page.getByPlaceholder('Search objects, evidence, blockers');
  await objectSearch.fill('current monitor');
  await objectSearch.press('Enter');
  await expect(page.getByText('current-monitor', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/object=current-monitor/);

  await objectSearch.fill('translation');
  await objectSearch.press('Enter');
  await expect(page.getByText('level-translation', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: /KiCad adapter-ready/ }).click();
  await expect(page.getByRole('heading', { name: 'KiCanvas' })).toBeVisible();
  await expect(page.getByText('Never owned', { exact: true })).toBeVisible();
  await expect(page.getByText('No matching renderable artifact is registered in this project revision.')).toBeVisible();
  await expect(page.getByText('Unresolved translation', { exact: true }).last()).toBeVisible();
  await expect(page).toHaveURL(/view=kicad/);

  await page.getByRole('button', { name: /Proposal adapter-ready/ }).click();
  await expect(page.getByRole('heading', { name: 'tscircuit / Circuit JSON' })).toBeVisible();
  await expect(page.getByText(/Conversion to KiCad requires an accepted deterministic action/)).toBeVisible();
  await expect(page.getByText('Authority effect')).toBeVisible();
  await expect(page.getByText('None', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/view=proposal/);

  await page.getByRole('button', { name: /System active/ }).click();
  await expect(page.getByText('Unresolved translation', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('level-translation', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/view=system/);
});
