const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const pagePath = path.join(root, 'app', 'engineering', 'source-lab', 'page.tsx');
const layoutPath = path.join(root, 'app', 'engineering', 'layout.tsx');
const parseProxyPath = path.join(
  root,
  'app',
  'api',
  'proxy',
  'engineering',
  'projects',
  '[projectId]',
  'sources',
  '[sourceId]',
  'parse',
  'route.ts',
);
const roleProxyPath = path.join(
  root,
  'app',
  'api',
  'proxy',
  'engineering',
  'projects',
  '[projectId]',
  'sources',
  '[sourceId]',
  'role',
  'route.ts',
);

for (const file of [pagePath, layoutPath, parseProxyPath, roleProxyPath]) {
  if (!fs.existsSync(file)) throw new Error(`Missing stored-source parser workspace file: ${file}`);
}

const page = fs.readFileSync(pagePath, 'utf8');
const layout = fs.readFileSync(layoutPath, 'utf8');
const parseProxy = fs.readFileSync(parseProxyPath, 'utf8');
const roleProxy = fs.readFileSync(roleProxyPath, 'utf8');

for (const contract of [
  'Source Lab',
  'Run bounded parser',
  'Apply role',
  'expected_revision',
  'authority_ceiling',
  'Role correction may preserve or lower authority, never raise it.',
  'STEP remains hash-verified inventory',
  '/parse',
  '/role',
]) {
  if (!page.includes(contract)) throw new Error(`Source Lab lost contract: ${contract}`);
}

if (!layout.includes('/engineering/source-lab')) {
  throw new Error('Engineering navigation does not expose Source Lab.');
}
if (!parseProxy.includes('/v1/projects/${encodeURIComponent(projectId)}/sources/${encodeURIComponent(sourceId)}/parse')) {
  throw new Error('Parser proxy does not target the canonical stored-source parser route.');
}
if (!roleProxy.includes('/v1/projects/${encodeURIComponent(projectId)}/sources/${encodeURIComponent(sourceId)}/role')) {
  throw new Error('Role proxy does not target the canonical source-role route.');
}
if (!parseProxy.includes('getProxyAuthHeaders') || !roleProxy.includes('getProxyAuthHeaders')) {
  throw new Error('Source Lab proxies do not preserve product authentication headers.');
}
if (page.includes('authority_ceiling: "verified"') || page.includes("authority_ceiling: 'verified'")) {
  throw new Error('Source Lab must not hard-code elevated upload authority.');
}
if (page.includes('motion_authorized: true') || page.includes('release_authorized: true')) {
  throw new Error('Source Lab must not hard-code physical authority.');
}

console.log('Stored-source parser workspace contract: OK');
