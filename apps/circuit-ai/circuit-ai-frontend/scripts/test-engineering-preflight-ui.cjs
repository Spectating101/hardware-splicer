const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const files = {
  page: path.join(root, 'app', 'engineering', 'preflight', 'page.tsx'),
  workbench: path.join(root, 'components', 'hs-preflight-workbench.tsx'),
  contract: path.join(root, 'lib', 'hs-preflight.ts'),
  layout: path.join(root, 'app', 'engineering', 'layout.tsx'),
  planProxy: path.join(root, 'app', 'api', 'proxy', 'engineering', 'plan', 'route.ts'),
  saveProxy: path.join(root, 'app', 'api', 'proxy', 'engineering', 'plans', 'save', 'route.ts'),
};
for (const [label, file] of Object.entries(files)) {
  if (!fs.existsSync(file)) throw new Error(`Missing HS Preflight ${label}: ${file}`);
}
const source = Object.fromEntries(Object.entries(files).map(([label, file]) => [label, fs.readFileSync(file, 'utf8')]));
const contracts = [
  [source.page, 'ssr: false', 'client-only file workflow boundary'],
  [source.workbench, 'Generate HS Preflight', 'real plan action'],
  [source.workbench, "fetch('/api/proxy/engineering/plan'", 'planning proxy call'],
  [source.workbench, "fetch('/api/proxy/engineering/plans/save'", 'persistence proxy call'],
  [source.workbench, 'Add URDF, SDF, MJCF', 'structured robot-model upload'],
  [source.workbench, 'Multiple structured models are attached', 'fail-closed model selection'],
  [source.workbench, 'Save revision', 'revision persistence control'],
  [source.workbench, 'Open inspector', 'Engineering inspector handoff'],
  [source.contract, 'compilePreflightRequest', 'native intake compiler'],
  [source.contract, 'physical_instances', 'starter physical-instance projection'],
  [source.contract, 'fabrication_artifacts', 'release-artifact projection'],
  [source.contract, 'selected_robot_model_source_id', 'explicit model selection'],
  [source.contract, 'summarizePlan', 'human-readable result summary'],
  [source.planProxy, '/v1/engineering/plan', 'canonical planning endpoint'],
  [source.saveProxy, '/v1/engineering/plans/save', 'canonical persistence endpoint'],
  [source.layout, '/engineering/preflight', 'discoverable Engineering navigation'],
];
for (const [text, fragment, label] of contracts) {
  if (!text.includes(fragment)) throw new Error(`HS Preflight lost ${label}: ${fragment}`);
}
if (source.workbench.includes('/execution/run') || source.workbench.includes('motion_authorized: true')) {
  throw new Error('Preflight must not invoke physical execution or hard-code motion authority.');
}
if (source.workbench.includes('href="/preflight"')) {
  throw new Error('A duplicate top-level Preflight route was reintroduced.');
}
console.log('HS Preflight UI contract: OK');
