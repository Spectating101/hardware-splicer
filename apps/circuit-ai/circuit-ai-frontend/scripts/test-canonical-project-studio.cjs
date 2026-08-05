const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const page = fs.readFileSync(path.join(root, 'app/engineering/studio/page.tsx'), 'utf8');
const launcher = fs.readFileSync(path.join(root, 'components/project-studio-launcher.tsx'), 'utf8');
const layout = fs.readFileSync(path.join(root, 'app/layout.tsx'), 'utf8');

const requiredPageText = [
  'What are you trying to build, verify, repair, or understand?',
  'Drop the files the project must actually respect',
  'Turn the brief and evidence into a reviewable candidate',
  'Ask from the exact project revision',
  'Export the current engineering history',
  'Next best move',
  'Physical authority',
  'Advanced details',
  '/api/proxy/engineering/projects',
  '/snapshot',
  '/sources/ingest-file',
  '/ai-sessions',
  '/decision',
  '/execute-preview',
  '/repair',
  '/turns',
  '/engineering-packages',
  'expected_revision',
  'automatic_authorization: false',
  'physical_authority_unchanged: true',
  'fabrication_authorized: false',
  'power_on_authorized: false',
  'release_authorized: false',
];

for (const value of requiredPageText) {
  if (!page.includes(value)) {
    throw new Error(`canonical Project Studio is missing contract text: ${value}`);
  }
}

for (const template of ['greenfield', 'validation', 'repair', 'robotics']) {
  if (!page.includes(`id: '${template}'`)) {
    throw new Error(`canonical Project Studio is missing onboarding template: ${template}`);
  }
}

for (const stage of ['Brief', 'Evidence', 'Candidate', 'Review', 'JARVIS', 'Package']) {
  if (!page.includes(`label: '${stage}'`)) {
    throw new Error(`canonical Project Studio is missing progress stage: ${stage}`);
  }
}

if (!launcher.includes('Start here') || !launcher.includes('/engineering/studio')) {
  throw new Error('global Project Studio launcher is missing its canonical route');
}
if (!layout.includes('<ProjectStudioLauncher />')) {
  throw new Error('root layout does not expose the canonical Project Studio');
}
if (!layout.includes('Evidence-governed AI engineering')) {
  throw new Error('root metadata does not describe the Hardware Splicer product boundary');
}

console.log('canonical Project Studio contract: PASS');
