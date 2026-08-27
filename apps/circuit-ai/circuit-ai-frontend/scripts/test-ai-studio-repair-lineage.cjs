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

const page = read('app/engineering/ai-studio/page.tsx');
const proxy = read('app/api/proxy/engineering/projects/[projectId]/ai-sessions/[sessionId]/actions/[actionId]/repair/route.ts');

requireText(page, 'Propose bounded repair', 'AI Studio');
requireText(page, 'Open repair successor', 'AI Studio');
requireText(page, 'Open failed parent', 'AI Studio');
requireText(page, "actionStatus === 'failed'", 'AI Studio');
requireText(page, "text(toolResult.status, '') === 'failed'", 'AI Studio');
requireText(page, 'previewActions.has(actionType)', 'AI Studio');
requireText(page, '/actions/${encodeURIComponent(actionId)}/repair', 'AI Studio');
requireText(page, 'expected_revision: revision', 'AI Studio');
requireText(page, 'max_actions: 6', 'AI Studio');
requireText(page, 'repair_session', 'AI Studio');
requireText(page, 'session_kind', 'AI Studio');
requireText(page, 'repair_of', 'AI Studio');
requireText(page, 'failure_sha256', 'AI Studio');
requireText(page, 'Successor candidate', 'AI Studio');
requireText(page, 'Repairs create successors; they never rewrite failed evidence or retry automatically.', 'AI Studio');
requireText(proxy, '/actions/${encodeURIComponent(actionId)}/repair', 'Repair proxy');
requireText(proxy, 'getProxyAuthHeaders(request)', 'Repair proxy');
requireText(proxy, 'forwardUiJsonResponse(response, target)', 'Repair proxy');

for (const forbidden of [
  'automatic_execution: true',
  'power_on_authorized: true',
  'motion_authorized: true',
  'release_authorized: true',
  'allow_llm_first: true',
  'export_gerber: true',
]) {
  if (page.includes(forbidden) || proxy.includes(forbidden)) {
    throw new Error(`AI repair UI contains forbidden authority fragment: ${forbidden}`);
  }
}

console.log('AI Studio repair lineage frontend contract passed.');
