const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8');

const files = {
  review: read('app/engineering/evidence/page.tsx'),
  compare: read('app/engineering/evidence/compare/page.tsx'),
  verify: read('app/engineering/evidence/verify/page.tsx'),
  bringup: read('app/engineering/evidence/bringup/page.tsx'),
  viewport: read('components/engineering/evidence-artifact-viewport.tsx'),
  nav: read('components/engineering/evidence-workspace-nav.tsx'),
};

function requireText(name, source, needle) {
  if (!source.includes(needle)) throw new Error(`${name} must contain ${JSON.stringify(needle)}`);
}

function forbidText(name, source, needle) {
  if (source.toLowerCase().includes(needle.toLowerCase())) {
    throw new Error(`${name} must not regress to ${JSON.stringify(needle)}`);
  }
}

// Artifact primacy / competitor parity.
requireText('review', files.review, 'kicanvas-embed');
requireText('viewport', files.viewport, 'EvidenceArtifactViewport');
requireText('viewport', files.viewport, "preferredKind?: PreferredArtifactKind");
requireText('compare', files.compare, 'Candidate artifact');
requireText('verify', files.verify, 'Verification ladder');
requireText('verify', files.verify, 'Physical correctness');
requireText('bringup', files.bringup, 'Validation sequence');
requireText('bringup', files.bringup, 'preferredKind="pcb"');

// One coherent workspace rather than disconnected product pages.
for (const label of ['Review', 'Compare', 'Verify', 'Bring-up']) requireText('workspace nav', files.nav, label);
requireText('workspace nav', files.nav, 'Deep inspect');

// HS-specific differentiation must remain visible above generic EDA/review parity.
for (const [name, source] of Object.entries({ review: files.review, verify: files.verify, bringup: files.bringup })) {
  requireText(name, source, 'Fabrication');
  requireText(name, source, 'Power');
}
requireText('compare', files.compare, 'No automatic merge');
requireText('compare', files.compare, 'review evidence, not merge authority');
requireText('bringup', files.bringup, 'test execution does not automatically change physical authority');

// Prevent regression to the prior AI-control-room aesthetic and internal strategy language.
const vnext = [files.review, files.compare, files.verify, files.bringup, files.nav].join('\n');
for (const forbidden of [
  'Hardware Splicer moat layer',
  'Contextual JARVIS inspector',
  'bg-[#020711]',
  'text-cyan-300',
  'text-violet-300',
  'text-fuchsia-300',
  'linear-gradient',
  'rounded-[1.6rem]',
]) forbidText('evidence workspace', vnext, forbidden);

console.log('competitive evidence workspace acceptance: PASS');
