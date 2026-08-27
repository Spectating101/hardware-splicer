const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const pagePath = path.join(root, 'app', 'engineering', 'uploads', 'page.tsx');
const layoutPath = path.join(root, 'app', 'engineering', 'layout.tsx');
const proxyPath = path.join(
  root,
  'app',
  'api',
  'proxy',
  'engineering',
  'projects',
  '[projectId]',
  'sources',
  'ingest-file',
  'route.ts',
);

for (const file of [pagePath, layoutPath, proxyPath]) {
  if (!fs.existsSync(file)) throw new Error(`Missing multipart upload file: ${file}`);
}

const page = fs.readFileSync(pagePath, 'utf8');
const layout = fs.readFileSync(layoutPath, 'utf8');
const proxy = fs.readFileSync(proxyPath, 'utf8');

for (const contract of [
  'Engineering Uploads',
  'FormData',
  'XMLHttpRequest',
  'xhr.upload.onprogress',
  'expected_revision',
  "form.append('file', item.file",
  "form.append('authority_ceiling', 'declared')",
  '/sources/ingest-file',
  'File exceeds the current 16 MiB multipart limit.',
  'Cancel active upload',
  'Files are sent directly as multipart bytes.',
  'fabrication_authorized: false',
  'motion_authorized: false',
  'release_authorized: false',
]) {
  if (!page.includes(contract)) throw new Error(`Multipart upload page lost contract: ${contract}`);
}

for (const forbidden of [
  'FileReader',
  'readAsDataURL',
  'content_base64',
  'btoa(',
]) {
  if (page.includes(forbidden)) throw new Error(`Multipart upload page contains forbidden base64 path: ${forbidden}`);
}

if (!layout.includes('/engineering/uploads')) {
  throw new Error('Engineering navigation does not expose multipart Uploads.');
}
if (!proxy.includes('/v1/projects/${encodeURIComponent(projectId)}/sources/ingest-file')) {
  throw new Error('Multipart proxy does not target the canonical ingest-file route.');
}
for (const contract of [
  'request.body',
  'duplex: "half"',
  'multipart/form-data',
  'getProxyAuthHeaders',
]) {
  if (!proxy.includes(contract)) throw new Error(`Multipart proxy lost streaming contract: ${contract}`);
}
if (proxy.includes('request.formData()') || proxy.includes('request.text()')) {
  throw new Error('Multipart proxy must forward the request stream without buffering or re-encoding it.');
}

console.log('Engineering multipart upload contract: OK');
