const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}

function assertIncludes(source, value, label) {
  if (!source.includes(value)) {
    throw new Error(`${label} is missing required contract: ${value}`);
  }
}

const page = read('app/engineering/page.tsx');
const helper = read('lib/engineering-status.ts');
const statusProxy = read('app/api/proxy/engineering/status/route.ts');
const diffProxy = read('app/api/proxy/engineering/revisions/diff/route.ts');
const projectsProxy = read('app/api/proxy/engineering/projects/route.ts');
const projectProxy = read('app/api/proxy/engineering/projects/[projectId]/route.ts');
const revisionsProxy = read('app/api/proxy/engineering/projects/[projectId]/revisions/route.ts');

for (const [source, label] of [
  [statusProxy, 'status proxy'],
  [diffProxy, 'revision diff proxy'],
  [projectsProxy, 'projects proxy'],
  [projectProxy, 'project proxy'],
  [revisionsProxy, 'revisions proxy'],
]) {
  assertIncludes(source, 'getHardwareSplicerApiUrl', label);
  assertIncludes(source, 'cache: "no-store"', label);
  assertIncludes(source, 'proxyUiFailureResponse', label);
}

assertIncludes(statusProxy, '/v1/engineering/status', 'status proxy');
assertIncludes(diffProxy, '/v1/engineering/revisions/diff', 'revision diff proxy');
assertIncludes(projectsProxy, '/v1/projects', 'projects proxy');
assertIncludes(projectProxy, 'encodeURIComponent(projectId)', 'project proxy');
assertIncludes(revisionsProxy, '/revisions', 'revisions proxy');

for (const contract of [
  "activeHref=\"/engineering\"",
  '/api/proxy/engineering/status',
  '/api/proxy/engineering/revisions/diff',
  '/api/proxy/engineering/projects',
  'manufacturing_closure',
  'engineering_execution_plan',
  'Physical gates remain closed',
  'Not authorized',
  'no automatic physical execution',
]) {
  assertIncludes(page, contract, 'engineering page');
}

for (const contract of [
  'extractEngineeringPlan',
  'safeParseEngineeringPlan',
  'sortNextActions',
  'summarizeRevisionDiff',
  'statusTone',
  'blockerTone',
]) {
  assertIncludes(helper, `export function ${contract}`, 'engineering helper');
}

if (page.includes('motion_authorized === true') === false) {
  throw new Error('engineering page must render the canonical motion authority gate');
}

if (page.includes("setProjectSource('local')") === false || page.includes("setProjectSource('persisted')") === false) {
  throw new Error('engineering page must distinguish local drafts from persisted revisions');
}

console.log('engineering status UI contract passed');
