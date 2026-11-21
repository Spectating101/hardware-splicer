#!/usr/bin/env node
// Usage: node scripts/verify_project_bench_browser.cjs <base-url> <output-dir> [saved-project-id]
// Requires Playwright and its Chromium runtime in the invoking environment.
const { mkdir } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

async function main() {
  const [baseUrl, outputDir, projectId] = process.argv.slice(2);
  if (!baseUrl || !outputDir) throw new Error('Expected <base-url> <output-dir> [saved-project-id]');
  await mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({headless:true});
  try {
    for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on('pageerror', (error) => errors.push(error.message));
      async function capture(name) {
        await page.waitForLoadState('networkidle');
        await page.evaluate(() => document.fonts.ready);
        const dimensions = await page.evaluate(() => ({
          page: document.documentElement.scrollWidth, viewport: document.documentElement.clientWidth,
        }));
        if (dimensions.page > dimensions.viewport) {
          throw new Error(`${name} at ${viewport.width}px overflows: ${JSON.stringify(dimensions)}`);
        }
        if (errors.length) throw new Error(errors.join('\n'));
        await page.screenshot({ path: path.join(outputDir, `${name}-${viewport.width}x${viewport.height}.png`), fullPage: true });
      }
      async function projectsHome() {
        await page.goto(baseUrl, { waitUntil: 'networkidle' });
        await page.getByTestId('home-start-project').waitFor();
        await page.getByRole('heading', { name: 'Saved projects', exact: true }).waitFor();
        await page.waitForFunction(() => !document.querySelector('[data-testid="home-start-project"]').disabled);
        await page.getByText(/Loading saved projects/).waitFor({ state: 'hidden' });
      }
      await projectsHome();
      await capture('home');
      await page.getByTestId('home-start-project').click();
      await page.getByTestId('new-project').waitFor();
      await capture('new-project');
      // Exercise the unit editor and the reference picker as well as the default goal intake.
      await page.getByRole('button', { name: 'Start from parts you have', exact: true }).click();
      await capture('new-project-parts');
      await page.getByRole('button', { name: 'Start from a reference study', exact: true }).click();
      await page.getByRole('button', { name: 'Start digital design', exact: true }).waitFor();
      await capture('new-project-reference');
      await projectsHome();
      const project = projectId
        ? page.locator(`button[data-project-id=${JSON.stringify(projectId)}]`)
        : page.locator('.project-rows button').first();
      if (!await project.count()) throw new Error('A real saved project is required for the bench capture; seed one or pass its id.');
      await project.click();
      await page.getByTestId('project-bench').waitFor({ timeout: 30000 });
      // Wait for revision-scoped evidence/material requests, including study loading.
      await page.waitForLoadState('networkidle');
      await capture('bench');
      if (viewport.width < 900) {
        for (const name of ['Parts', 'Design', 'Evidence']) {
          await page.getByRole('tab', { name, exact: true }).click();
          await capture(`bench-${name.toLowerCase()}`);
        }
        const headerHeight = await page.locator('.sidebar').evaluate((element) => element.getBoundingClientRect().height);
        if (headerHeight > 100) throw new Error(`Mobile header is too tall: ${headerHeight}px`);
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }
}
main().catch((error) => { console.error(error.message); process.exitCode = 1; });
