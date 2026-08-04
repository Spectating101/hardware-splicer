const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const sourcesPagePath = path.join(root, 'app', 'engineering', 'sources', 'page.tsx');
const projectPreflightPath = path.join(root, 'app', 'engineering', 'project-preflight', 'page.tsx');
const layoutPath = path.join(root, 'app', 'engineering', 'layout.tsx');
const uploadProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'sources', 'ingest', 'route.ts');
const snapshotProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'snapshot', 'route.ts');
const projectPlanProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'plan', 'route.ts');

for (const file of [sourcesPagePath, projectPreflightPath, layoutPath, uploadProxyPath, snapshotProxyPath, projectPlanProxyPath]) {
  if (!fs.existsSync(file)) throw new Error(`Missing project engineering workspace file: ${file}`);
}

const sourcesPage = fs.readFileSync(sourcesPagePath, 'utf8');
const projectPreflight = fs.readFileSync(projectPreflightPath, 'utf8');
const layout = fs.readFileSync(layoutPath, 'utf8');
const uploadProxy = fs.readFileSync(uploadProxyPath, 'utf8');
const snapshotProxy = fs.readFileSync(snapshotProxyPath, 'utf8');
const projectPlanProxy = fs.readFileSync(projectPlanProxyPath, 'utf8');

const sourcePageContracts = [
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

for (const contract of sourcePageContracts) {
  if (!sourcesPage.includes(contract)) throw new Error(`Engineering Sources page lost contract: ${contract}`);
}

const projectPlanContracts = [
  'Project Preflight',
  'Generate and save',
  'expected_revision: revision',
  'additional_engineering_sources: []',
  '/plan',
  'Saved revision',
  'fabrication_authorized',
  'motion_authorized',
  'release_authorized',
];

for (const contract of projectPlanContracts) {
  if (!projectPreflight.includes(contract)) throw new Error(`Project Preflight lost contract: ${contract}`);
}

for (const href of ['/engineering/sources', '/engineering/project-preflight']) {
  if (!layout.includes(href)) throw new Error(`Engineering navigation does not expose ${href}.`);
}
if (!uploadProxy.includes('/v1/projects/${encodeURIComponent(projectId)}/sources/ingest')) {
  throw new Error('Source upload proxy does not target the canonical ingestion route.');
}
if (!snapshotProxy.includes('/v1/projects/${encodeURIComponent(projectId)}/snapshot')) {
  throw new Error('Snapshot proxy does not target optimistic project persistence.');
}
if (!projectPlanProxy.includes('/v1/projects/${encodeURIComponent(projectId)}/engineering/plan')) {
  throw new Error('Project plan proxy does not target persisted guided planning.');
}
if (![uploadProxy, snapshotProxy, projectPlanProxy].every((value) => value.includes('getProxyAuthHeaders'))) {
  throw new Error('Project engineering proxies do not preserve product proxy authentication headers.');
}
const combinedPages = `${sourcesPage}\n${projectPreflight}`;
if (combinedPages.includes('fabrication_authorized: true') || combinedPages.includes('motion_authorized: true') || combinedPages.includes('release_authorized: true')) {
  throw new Error('Project engineering workspaces must not hard-code physical authority.');
}

console.log('Project engineering workspace contract: OK');
