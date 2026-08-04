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
const layout = read('app/engineering/layout.tsx');
const createProxy = read('app/api/proxy/engineering/projects/[projectId]/ai-sessions/route.ts');
const getProxy = read('app/api/proxy/engineering/projects/[projectId]/ai-sessions/[sessionId]/route.ts');
const decisionProxy = read('app/api/proxy/engineering/projects/[projectId]/ai-sessions/[sessionId]/actions/[actionId]/decision/route.ts');

requireText(page, 'AI Project Studio', 'AI Studio page');
requireText(page, 'Generate proposals', 'AI Studio page');
requireText(page, 'Accept proposal', 'AI Studio page');
requireText(page, 'Recorded without execution.', 'AI Studio page');
requireText(page, 'Automatic execution is disabled.', 'AI Studio page');
requireText(page, 'expected_revision: revision', 'AI Studio page');
requireText(page, "model_profile: modelProfile", 'AI Studio page');
requireText(page, "decideAction(actionId, 'accepted')", 'AI Studio page');
requireText(page, 'No tool execution authorized.', 'AI Studio page');
requireText(layout, 'href="/engineering/ai-studio"', 'Engineering navigation');
requireText(createProxy, '/v1/projects/${encodeURIComponent(projectId)}/ai-sessions', 'Session creation proxy');
requireText(getProxy, '/ai-sessions/${encodeURIComponent(sessionId)}', 'Session retrieval proxy');
requireText(decisionProxy, '/actions/${encodeURIComponent(actionId)}/decision', 'Action decision proxy');
requireText(createProxy, 'getProxyAuthHeaders(request)', 'Session creation proxy');
requireText(getProxy, 'getProxyAuthHeaders(request)', 'Session retrieval proxy');
requireText(decisionProxy, 'getProxyAuthHeaders(request)', 'Action decision proxy');

for (const forbidden of ['power_on: true', 'motion_authorized: true', 'release_authorized: true', 'automatic_execution: true']) {
  if (page.includes(forbidden)) {
    throw new Error(`AI Studio page contains forbidden authority fragment: ${forbidden}`);
  }
}

console.log('AI Project Studio frontend contract passed.');
