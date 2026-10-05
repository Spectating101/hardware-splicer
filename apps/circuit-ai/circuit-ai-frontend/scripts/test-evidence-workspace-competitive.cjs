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
  threads: read('components/engineering/review-threads-panel.tsx'),
  provenance: read('components/engineering/provenance-chip.tsx'),
  overlay: read('components/engineering/viewer-overlay.tsx'),
  changes: read('components/engineering/artifact-changes-panel.tsx'),
  diffLib: read('lib/artifact-diff.ts'),
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
// Review shares one viewer with Compare, Verify and Bring-up instead of carrying its own copy.
requireText('review', files.review, 'EvidenceArtifactViewport');
forbidText('review', files.review, 'useKiCanvasScript');
requireText('viewport', files.viewport, 'kicanvas-embed');
requireText('viewport', files.viewport, 'EvidenceArtifactViewport');
requireText('viewport', files.viewport, "preferredKind?: PreferredArtifactKind");
requireText('viewport', files.viewport, 'Read-only review');
requireText('viewport', files.viewport, "controlslist', 'nodownload nooverlay'");
requireText('compare', files.compare, 'Candidate artifact');
requireText('verify', files.verify, 'Verification ladder');
requireText('verify', files.verify, 'Physical correctness');
requireText('bringup', files.bringup, 'Validation sequence');
requireText('bringup', files.bringup, 'preferredKind="pcb"');

// One coherent workspace rather than disconnected product pages.
for (const label of ['Review', 'Compare', 'Verify', 'Bring-up']) requireText('workspace nav', files.nav, label);
requireText('workspace nav', files.nav, 'Deep inspect');

// Orientation, evidence-to-claim locality and keyboard-first review (added from the 2026-10 competitor pass).
requireText('review', files.review, 'data-testid="next-step"');
requireText('review', files.review, 'Cited by');
requireText('review', files.review, 'No recorded requirement cites this source.');
requireText('review', files.review, "event.key === 'j'");
requireText('workspace nav', files.nav, 'Copy link');
requireText('workspace nav', files.nav, "['1', '2', '3', '4']");
// The strip may describe state but must never offer a way to open authority.
const nextStepStart = files.review.indexOf('data-testid="next-step"');
const nextStepEnd = files.review.indexOf('{error ? (', nextStepStart);
const nextStepSource = files.review.slice(nextStepStart, nextStepEnd);
if (/>\s*(Authorize|Approve|Accept|Fabricate|Power on)\b/i.test(nextStepSource)) {
  throw new Error('review next step must not offer an authority action');
}

// Discussion and provenance (backend: project_thread_store.py, finding_provenance.py). Both are labels or
// conversation only; neither may offer an authority action or imply a verified identity.
requireText('review', files.review, 'ReviewThreadsPanel');
requireText('review', files.review, 'ProvenanceChip');
requireText('threads', files.threads, 'Comments never change findings, evidence or authority.');
requireText('threads', files.threads, 'Names are self-declared and not verified.');
requireText('threads', files.threads, 'expected_event_seq');
requireText('provenance', files.provenance, 'Provenance not recorded');
requireText('provenance', files.provenance, 'never whether it is correct');
for (const [name, source] of [['threads panel', files.threads], ['provenance chip', files.provenance]]) {
  if (/>\s*(Authorize|Approve|Accept|Fabricate|Power on|Release)\b/i.test(source)) {
    throw new Error(`${name} must not offer an authority action`);
  }
}
// An unlabeled finding must read as unknown, never as a flattering default.
if (/provenance\s*\?\?\s*['"]deterministic['"]/.test(files.provenance + files.review)) {
  throw new Error('unlabeled findings must not default to deterministic');
}

// Position pins, operator tokens and artifact redlines (see backend: kicad_diff.py, operator_identity.py).
requireText('overlay', files.overlay, 'world_to_screen');
requireText('overlay', files.overlay, 'never identifies a board object');
requireText('overlay', files.overlay, 'Rotated or flipped views are not drawn rather than drawn wrongly');
requireText('threads', files.threads, 'x-hs-operator-token');
requireText('threads', files.threads, 'sessionStorage');
requireText('changes', files.changes, 'A diff is review evidence, not a verdict');
requireText('changes', files.changes, 'Not compared.');
requireText('diff lib', files.diffLib, 'Missing artifacts are reported, never guessed');
requireText('compare', files.compare, 'ArtifactChangesPanel');
for (const [name, source] of [['overlay', files.overlay], ['artifact changes', files.changes], ['diff lib', files.diffLib]]) {
  if (/>\s*(Authorize|Approve|Accept|Fabricate|Power on|Release)\b/i.test(source)) {
    throw new Error(`${name} must not offer an authority action`);
  }
}
// The operator token is a credential: never written to local storage or logged.
if (/localStorage\.setItem\(\s*TOKEN_KEY/.test(files.threads) || /console\.(log|debug|info)\([^)]*token/i.test(files.threads)) {
  throw new Error('operator token must stay in session storage and out of logs');
}

// HS-specific differentiation must remain visible above generic EDA/review parity.
// Do not force long prose labels where the compact professional UI intentionally uses FAB / POWER / RELEASE.
requireText('review', files.review, "statusChip('Fabrication'");
requireText('review', files.review, "statusChip('Power-on'");
requireText('verify', files.verify, 'FAB<br />');
requireText('verify', files.verify, 'POWER<br />');
requireText('verify', files.verify, 'RELEASE<br />');
requireText('bringup', files.bringup, 'Fabrication');
requireText('bringup', files.bringup, 'Power-on');
requireText('bringup', files.bringup, 'RELEASE<br />');
requireText('compare', files.compare, 'No automatic merge');
requireText('compare', files.compare, 'review evidence, not merge authority');
requireText('bringup', files.bringup, 'Measurements update evidence state; authority changes only through the explicit review boundary.');

// Strategic restraint: HS is a review / evidence / release-assurance surface, not a replacement ECAD editor.
// Keep the central artifact visible and inspectable while source-of-truth editing remains outside this viewport.
for (const forbidden of [
  'Edit schematic',
  'Edit PCB',
  'Save schematic',
  'Save PCB',
  'Route trace',
  'Place component',
]) forbidText('artifact viewport', files.viewport, forbidden);

// Prevent regression to the prior AI-control-room aesthetic and internal strategy language.
const vnext = [files.review, files.compare, files.verify, files.bringup, files.nav].join('\n');
for (const forbidden of [
  'Hardware Splicer moat layer',
  'Contextual JARVIS inspector',
  'Unlike generic HIL dashboards',
  'bg-[#020711]',
  'text-cyan-300',
  'text-violet-300',
  'text-fuchsia-300',
  'linear-gradient',
  'rounded-[1.6rem]',
]) forbidText('evidence workspace', vnext, forbidden);

console.log('competitive evidence workspace acceptance: PASS');
