const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const pagePath = path.join(root, 'app', 'engineering', 'resumable-uploads', 'page.tsx');
const layoutPath = path.join(root, 'app', 'engineering', 'layout.tsx');
const createProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'source-upload-sessions', 'route.ts');
const sessionProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'source-upload-sessions', '[sessionId]', 'route.ts');
const chunkProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'source-upload-sessions', '[sessionId]', 'chunks', '[chunkIndex]', 'route.ts');
const finalizeProxyPath = path.join(root, 'app', 'api', 'proxy', 'engineering', 'projects', '[projectId]', 'source-upload-sessions', '[sessionId]', 'finalize', 'route.ts');

for (const file of [pagePath, layoutPath, createProxyPath, sessionProxyPath, chunkProxyPath, finalizeProxyPath]) {
  if (!fs.existsSync(file)) throw new Error(`Missing resumable upload file: ${file}`);
}

const page = fs.readFileSync(pagePath, 'utf8');
const layout = fs.readFileSync(layoutPath, 'utf8');
const createProxy = fs.readFileSync(createProxyPath, 'utf8');
const sessionProxy = fs.readFileSync(sessionProxyPath, 'utf8');
const chunkProxy = fs.readFileSync(chunkProxyPath, 'utf8');
const finalizeProxy = fs.readFileSync(finalizeProxyPath, 'utf8');

for (const contract of [
  'Resumable Uploads',
  "crypto.subtle.digest('SHA-256'",
  'expected_content_hash',
  'expected_revision',
  "authority_ceiling: 'declared'",
  'Upload missing chunks',
  'Cancel active chunk',
  'Reconcile and finalize',
  'Abandon session',
  'No project mutation before finalize',
  'source-upload-sessions',
  'x-chunk-sha256',
  'localStorage.setItem',
]) {
  if (!page.includes(contract)) throw new Error(`Resumable upload page lost contract: ${contract}`);
}

for (const forbidden of ['content_base64', 'readAsDataURL', 'btoa(']) {
  if (page.includes(forbidden)) throw new Error(`Resumable upload page contains forbidden base64 path: ${forbidden}`);
}

if (!layout.includes('/engineering/resumable-uploads')) {
  throw new Error('Engineering navigation does not expose resumable uploads.');
}
if (!createProxy.includes('/source-upload-sessions')) {
  throw new Error('Session creation proxy lost its canonical backend target.');
}
if (!sessionProxy.includes('method: "DELETE"') || !sessionProxy.includes('method: "GET"')) {
  throw new Error('Session proxy must support status and abandonment.');
}
for (const contract of ['request.body', 'duplex: "half"', 'x-chunk-sha256', 'getProxyAuthHeaders']) {
  if (!chunkProxy.includes(contract)) throw new Error(`Chunk proxy lost raw streaming contract: ${contract}`);
}
if (chunkProxy.includes('request.text()') || chunkProxy.includes('request.formData()')) {
  throw new Error('Chunk proxy must not buffer or re-encode the raw chunk body.');
}
if (!finalizeProxy.includes('/finalize') || !finalizeProxy.includes('getProxyAuthHeaders')) {
  throw new Error('Finalize proxy lost canonical routing or authentication.');
}

console.log('Resumable source upload workspace contract: OK');
