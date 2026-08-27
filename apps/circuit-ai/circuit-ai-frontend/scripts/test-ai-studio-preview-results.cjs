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
const proxy = read('app/api/proxy/engineering/projects/[projectId]/ai-sessions/[sessionId]/actions/[actionId]/execute-preview/route.ts');

requireText(page, "const previewActions = new Set(['run_guided_plan', 'run_compose'])", 'AI Studio');
requireText(page, 'Run software preview', 'AI Studio');
requireText(page, 'expected_revision: revision', 'AI Studio');
requireText(page, '/execute-preview', 'AI Studio');
requireText(page, 'actionStatus === \'accepted\'', 'AI Studio');
requireText(page, '!action.tool_result', 'AI Studio');
requireText(page, 'Software preview', 'AI Studio');
requireText(page, 'artifact.project_relative_path', 'AI Studio');
requireText(page, 'artifact.sha256', 'AI Studio');
requireText(page, 'Software evidence only · physical authority unchanged', 'AI Studio');
requireText(page, 'Accepted as a proposal only. Software preview requires a separate action.', 'AI Studio');
requireText(proxy, '/actions/${encodeURIComponent(actionId)}/execute-preview', 'Preview proxy');
requireText(proxy, 'getProxyAuthHeaders(request)', 'Preview proxy');
requireText(proxy, 'forwardUiJsonResponse', 'Preview proxy');

for (const forbidden of [
  'allow_llm_first: true',
  'export_gerber: true',
  'automatic_execution: true',
  'power_on_authorized: true',
  'motion_authorized: true',
  'release_authorized: true',
]) {
  if (page.includes(forbidden) || proxy.includes(forbidden)) {
    throw new Error(`Preview UI contains forbidden authority fragment: ${forbidden}`);
  }
}

console.log('AI Studio preview result contract passed.');
