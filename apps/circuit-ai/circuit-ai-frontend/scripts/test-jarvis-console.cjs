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

const page = read('app/engineering/jarvis/page.tsx');
const layout = read('app/engineering/layout.tsx');
const proxy = read('app/api/proxy/engineering/projects/[projectId]/ai-sessions/[sessionId]/turns/route.ts');

requireText(page, 'JARVIS Console', 'JARVIS page');
requireText(page, 'Ask JARVIS', 'JARVIS page');
requireText(page, 'JARVIS is guidance, not project truth.', 'JARVIS page');
requireText(page, 'human review, deterministic preview, physical evidence, and authority remain separate', 'JARVIS page');
requireText(page, 'expected_revision: revision', 'JARVIS page');
requireText(page, 'client_request_id: clientRequestId', 'JARVIS page');
requireText(page, 'max_proposals: 2', 'JARVIS page');
requireText(page, 'conversationTurns', 'JARVIS page');
requireText(page, 'evidence_refs', 'JARVIS page');
requireText(page, 'recommended_action_id', 'JARVIS page');
requireText(page, 'origin_turn_id', 'JARVIS page');
requireText(page, 'Awaiting human review', 'JARVIS page');
requireText(page, 'Review in AI Studio', 'JARVIS page');
requireText(layout, 'href="/engineering/jarvis"', 'Engineering navigation');
requireText(layout, 'JARVIS', 'Engineering navigation');
requireText(proxy, '/ai-sessions/${encodeURIComponent(sessionId)}/turns', 'JARVIS proxy');
requireText(proxy, 'getProxyAuthHeaders(request)', 'JARVIS proxy');
requireText(proxy, 'forwardUiJsonResponse(response, target)', 'JARVIS proxy');

for (const forbidden of [
  'automatic_execution: true',
  'power_on_authorized: true',
  'motion_authorized: true',
  'release_authorized: true',
  'allow_llm_first: true',
  'export_gerber: true',
]) {
  if (page.includes(forbidden) || proxy.includes(forbidden)) {
    throw new Error(`JARVIS surface contains forbidden authority fragment: ${forbidden}`);
  }
}

console.log('JARVIS engineering console contract passed.');
