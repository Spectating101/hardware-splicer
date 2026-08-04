const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const pagePath = path.join(root, 'app', 'engineering', 'storage-ops', 'page.tsx');
const layoutPath = path.join(root, 'app', 'engineering', 'layout.tsx');
const auditProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'source-storage', 'audit', 'route.ts');
const cleanupProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'source-storage', 'cleanup', 'route.ts');

for (const file of [pagePath, layoutPath, auditProxyPath, cleanupProxyPath]) {
  if (!fs.existsSync(file)) throw new Error(`Missing source storage operations file: ${file}`);
}

const page = fs.readFileSync(pagePath, 'utf8');
const layout = fs.readFileSync(layoutPath, 'utf8');
const auditProxy = fs.readFileSync(auditProxyPath, 'utf8');
const cleanupProxy = fs.readFileSync(cleanupProxyPath, 'utf8');

for (const contract of [
  'Source Storage Ops',
  'Audit storage',
  'Preview cleanup',
  'Apply confirmed cleanup',
  'confirm_project_id',
  'minimum_age_hours',
  'include_corrupt_orphans',
  'Referenced blobs are never cleanup candidates.',
  'Automatic deletion is disabled.',
  'audit and cleanup do not create a project revision',
]) {
  if (!page.includes(contract)) throw new Error(`Storage Ops page lost contract: ${contract}`);
}
if (!page.includes('confirmation !== projectId.trim()')) {
  throw new Error('Destructive Storage Ops button is not gated by exact project confirmation.');
}
if (!layout.includes('/engineering/storage-ops')) {
  throw new Error('Engineering navigation does not expose Storage Ops.');
}
if (!auditProxy.includes('/source-storage/audit') || !auditProxy.includes('getProxyAuthHeaders')) {
  throw new Error('Storage audit proxy lost canonical routing or authentication.');
}
if (!cleanupProxy.includes('/source-storage/cleanup') || !cleanupProxy.includes('getProxyAuthHeaders')) {
  throw new Error('Storage cleanup proxy lost canonical routing or authentication.');
}
if (page.includes('automatic_deletion: true') || page.includes('project_revision_mutated: true')) {
  throw new Error('Storage Ops must not hard-code automatic deletion or project revision mutation.');
}

console.log('Source storage operations workspace contract: OK');
