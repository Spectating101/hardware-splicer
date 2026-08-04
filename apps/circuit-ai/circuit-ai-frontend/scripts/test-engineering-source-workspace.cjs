const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const pagePath = path.join(root, 'app', 'engineering', 'sources', 'page.tsx');
const layoutPath = path.join(root, 'app', 'engineering', 'layout.tsx');
const uploadProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'sources', 'ingest', 'route.ts');
const snapshotProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'snapshot', 'route.ts');

for (const file of [pagePath, layoutPath, uploadProxyPath, snapshotProxyPath]) {
  if (!fs.existsSync(file)) throw new Error(`Missing Engineering Sources workspace file: ${file}`);
}

const page = fs.readFileSync(pagePath, 'utf8');
const layout = fs.readFileSync(layoutPath, 'utf8');
const uploadProxy = fs.readFileSync(uploadProxyPath, 'utf8');
const snapshotProxy = fs.readFileSync(snapshotProxyPath, 'utf8');

const pageContracts = [
  'Engineering Sources',
  'XMLHttpRequest',
  'expected_revision',
  'content_base64',
  'authority_ceiling',
  "authority_ceiling: 'declared'",
  'File exceeds the current 16 MiB ingestion limit.',
  'Upload pending',
  'Download manifest',
  'fabrication_authorized: false',
  'motion_authorized: false',
  'release_authorized: false',
];

for (const contract of pageContracts) {
  if (!page.includes(contract)) throw new Error(`Engineering Sources page lost contract: ${contract}`);
}

if (!layout.includes('/engineering/sources')) {
  throw new Error('Engineering navigation does not expose the Sources workspace.');
}
if (!uploadProxy.includes('/v1/projects/${encodeURIComponent(projectId)}/sources/ingest')) {
  throw new Error('Source upload proxy does not target the canonical ingestion route.');
}
if (!snapshotProxy.includes('/v1/projects/${encodeURIComponent(projectId)}/snapshot')) {
  throw new Error('Snapshot proxy does not target optimistic project persistence.');
}
if (!uploadProxy.includes('getProxyAuthHeaders') || !snapshotProxy.includes('getProxyAuthHeaders')) {
  throw new Error('Project source proxies do not preserve product proxy authentication headers.');
}
if (page.includes('fabrication_authorized: true') || page.includes('motion_authorized: true') || page.includes('release_authorized: true')) {
  throw new Error('Engineering Sources must not hard-code physical authority.');
}

console.log('Engineering Sources workspace contract: OK');
