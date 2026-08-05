const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const pagePath = path.join(root, 'app/engineering/visual/page.tsx');
const canvasPath = path.join(root, 'components/engineering/canonical-system-canvas.tsx');
const adaptersPath = path.join(root, 'lib/engineering-visual-adapters.ts');
const launcherPath = path.join(root, 'components/project-studio-launcher.tsx');

for (const file of [pagePath, canvasPath, adaptersPath, launcherPath]) {
  if (!fs.existsSync(file)) throw new Error(`Missing visual workbench file: ${file}`);
}

const page = fs.readFileSync(pagePath, 'utf8');
const canvas = fs.readFileSync(canvasPath, 'utf8');
const adapters = fs.readFileSync(adaptersPath, 'utf8');
const launcher = fs.readFileSync(launcherPath, 'utf8');

const pageContracts = [
  'Visual Engineering Workbench',
  'Hardware Splicer moat layer',
  'CanonicalSystemCanvas',
  'Contextual JARVIS inspector',
  'Revision and tool timeline',
  'Viewers grant no authority',
  "activeView === 'system'",
  'selectedObjectId={selectedInCurrentGraph?.id}',
  'onSelectObject={setSelectedObject}',
  'Project truth',
  'Authority effect',
  'Never owned',
];
for (const contract of pageContracts) {
  if (!page.includes(contract)) throw new Error(`Visual page is missing contract: ${contract}`);
}

const canvasContracts = [
  'deriveCanonicalSystemGraph',
  'fixture-controller',
  'level-translation',
  'dut-socket',
  'current-monitor',
  'test-equipment',
  'evidenceIds',
  'proposalIds',
  "authority: 'none'",
  'Select an object to inspect evidence, blockers, proposal lineage, and cross-view identity.',
  'nodesConnectable={false}',
  'deleteKeyCode={null}',
];
for (const contract of canvasContracts) {
  if (!canvas.includes(contract)) throw new Error(`System canvas is missing contract: ${contract}`);
}

const adapterContracts = [
  "project: 'React Flow'",
  "project: 'KiCanvas'",
  "project: 'tscircuit / Circuit JSON'",
  "project: 'React Three Fiber / Three.js'",
  "project: 'tracespace'",
  "project: 'InteractiveHtmlBom'",
  'ownsProjectTruth: false',
  "authorityEffect: 'none'",
  'Bundle must be pinned and self-hosted before production enablement.',
  'Conversion to KiCad requires an accepted deterministic action and native KiCad validation.',
];
for (const contract of adapterContracts) {
  if (!adapters.includes(contract)) throw new Error(`Adapter registry is missing contract: ${contract}`);
}

const forbiddenPageMutations = [
  '/execute-preview',
  '/decision',
  '/repair',
  '/snapshot',
  'method: \'POST\'',
  'method: \'PUT\'',
  'method: \'PATCH\'',
  'method: \'DELETE\'',
];
for (const forbidden of forbiddenPageMutations) {
  if (page.includes(forbidden)) throw new Error(`Visual workbench must remain read-only; found ${forbidden}`);
}

if (!launcher.includes("href = insideStudio ? '/engineering/visual' : '/engineering/studio'")) {
  throw new Error('Project Studio launcher does not expose the visual workbench.');
}

console.log('Visual engineering workbench contract is intact.');
