const path = require('node:path');

const output = process.env.HS_FRONTEND_VERIFY_DIR;
if (!output) throw new Error('Run through scripts/verify_device_frontend.sh to isolate test output.');

module.exports = {
  testDir: path.join(__dirname, 'e2e'),
  timeout: 90000,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: path.join(output, 'playwright-report.json') }]],
  use: { headless: true, browserName: 'chromium', screenshot: 'only-on-failure' },
  outputDir: path.join(output, 'playwright-output'),
};
