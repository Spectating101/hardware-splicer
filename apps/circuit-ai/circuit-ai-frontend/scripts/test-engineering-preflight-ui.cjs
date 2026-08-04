const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const pagePath = path.join(root, 'app', 'engineering', 'preflight', 'page.tsx');
const layoutPath = path.join(root, 'app', 'engineering', 'layout.tsx');
const proxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'plan', 'route.ts');

for (const file of [pagePath, layoutPath, proxyPath]) {
  if (!fs.existsSync(file)) throw new Error(`Missing HS Preflight interface file: ${file}`);
}

const page = fs.readFileSync(pagePath, 'utf8');
const layout = fs.readFileSync(layoutPath, 'utf8');
const proxy = fs.readFileSync(proxyPath, 'utf8');

const requiredPageContracts = [
  'HS Preflight',
  'Load rover demo',
  'Run preflight',
  '/api/proxy/engineering/plan',
  'Import JSON',
  'Download report',
  "const tabs = ['Summary', 'Sources', 'Topology', 'Closure', 'Guide', 'Raw']",
  'fabrication_authorized',
  'motion_authorized',
  'release_authorized',
  'Binary CAD, PCB and media upload requires the next file-ingestion tranche',
];

for (const contract of requiredPageContracts) {
  if (!page.includes(contract)) throw new Error(`Preflight page lost contract: ${contract}`);
}

if (!layout.includes('/engineering/preflight')) {
  throw new Error('Engineering layout does not expose HS Preflight navigation.');
}
if (!proxy.includes('/v1/engineering/plan')) {
  throw new Error('Preflight proxy does not target the canonical engineering plan endpoint.');
}
if (!proxy.includes('getProxyAuthHeaders')) {
  throw new Error('Preflight proxy does not preserve product proxy authentication headers.');
}
for (const contract of [
  'normalizeDiscoverySources',
  'discovery_only: true',
  'requires_concrete_source_selection: true',
  'requires_timestamp_range_for_media_observation: true',
  'authority_ceiling: "declared"',
  'claims: []',
]) {
  if (!proxy.includes(contract)) throw new Error(`Preflight proxy lost discovery-authority contract: ${contract}`);
}
if (page.includes('/execution/run') || page.includes('flash_authorized: true') || page.includes('motion_authorized: true')) {
  throw new Error('Preflight UI must not directly invoke execution or hard-code physical authority.');
}

console.log('HS Preflight UI contract: OK');
