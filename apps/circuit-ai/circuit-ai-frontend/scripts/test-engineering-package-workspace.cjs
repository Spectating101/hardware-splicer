const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}

function requireText(content, fragment, label) {
  if (!content.includes(fragment)) {
    throw new Error(`${label} is missing required fragment: ${fragment}`);
  }
}

const page = read('app/engineering/packages/page.tsx');
const layout = read('app/engineering/layout.tsx');
const collectionProxy = read('app/api/proxy/engineering/projects/[projectId]/engineering-packages/route.ts');
const downloadProxy = read('app/api/proxy/engineering/projects/[projectId]/engineering-packages/[packageId]/download/route.ts');

requireText(page, 'Engineering Packages', 'Package workspace');
requireText(page, 'Export revision', 'Package workspace');
requireText(page, 'expected_revision: sourceRevision', 'Package workspace');
requireText(page, 'Snapshot SHA-256', 'Package workspace');
requireText(page, 'Manifest SHA-256', 'Package workspace');
requireText(page, 'ZIP SHA-256', 'Package workspace');
requireText(page, 'Raw source bytes: excluded', 'Package workspace');
requireText(page, 'Authority effect:', 'Package workspace');
requireText(page, 'Downloads are served only after backend size and SHA-256 verification.', 'Package workspace');
requireText(page, '/engineering-packages/${encodeURIComponent(packageId)}/download', 'Package workspace');
requireText(layout, 'href="/engineering/packages"', 'Engineering navigation');
requireText(layout, 'Packages', 'Engineering navigation');
requireText(layout, 'overflow-x-auto', 'Engineering navigation');
requireText(collectionProxy, '/engineering-packages', 'Package collection proxy');
requireText(collectionProxy, 'getProxyAuthHeaders(request)', 'Package collection proxy');
requireText(downloadProxy, '/engineering-packages/${encodeURIComponent(packageId)}/download', 'Package download proxy');
requireText(downloadProxy, 'getProxyAuthHeaders(request)', 'Package download proxy');
requireText(downloadProxy, 'new Response(response.body', 'Package download proxy');
requireText(downloadProxy, 'x-hardware-splicer-package-sha256', 'Package download proxy');
requireText(downloadProxy, 'x-hardware-splicer-source-revision', 'Package download proxy');

for (const forbidden of [
  'automatic_execution: true',
  'power_on_authorized: true',
  'motion_authorized: true',
  'release_authorized: true',
  'allow_llm_first: true',
  'export_gerber: true',
  'raw_source_bytes_included: true',
]) {
  if (page.includes(forbidden) || collectionProxy.includes(forbidden) || downloadProxy.includes(forbidden)) {
    throw new Error(`Engineering Package workspace contains forbidden fragment: ${forbidden}`);
  }
}

console.log('Engineering Package workspace contract passed.');
