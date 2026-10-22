import { deriveProjectTruth } from "./deriveProjectTruth.js";
import { derivePackageHandoff } from "./packageHandoff.js";

/**
 * Read-only projection of the existing persisted HS session and real package.
 * Missing fields stay missing; this layer never generates specifications,
 * evidence, verification results or physical authorization.
 */
export const PROJECT_REVIEW_TABS = Object.freeze([
  { id: "overview", label: "Overview" },
  { id: "parts", label: "Parts" },
  { id: "wiring", label: "Wiring" },
  { id: "mechanical", label: "Mechanical" },
  { id: "code", label: "Code" },
  { id: "build", label: "Build" },
  { id: "verify", label: "Verify" },
]);

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function rows(value) {
  return Array.isArray(value) ? value : [];
}

function label(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function normalizeSha256(value) {
  const raw = label(value);
  if (!raw) return null;
  const digest = raw.replace(/^sha256:/i, "");
  return /^[0-9a-f]{64}$/i.test(digest) ? digest.toLowerCase() : null;
}

function sourceRows(pkg) {
  const sources = [
    ...rows(pkg.sources),
    ...rows(pkg.source_descriptors),
    ...rows(object(pkg.evidence).sources),
    ...Object.entries(object(pkg.source))
      .filter(([key]) => key.endsWith("_sha256"))
      .map(([key, sha256]) => ({ source_id: key, sha256 })),
  ];
  const seen = new Set();
  return sources.flatMap((entry) => {
    const source = object(entry);
    const key = normalizeSha256(source.sha256) || normalizeSha256(source.content_hash);
    // A source label without a valid content identity must not look verified.
    if (!key) return [];
    if (seen.has(key)) return [];
    seen.add(key);
    return [{
      id: label(source.source_id) || label(source.id) || label(source.name) || "Source",
      sha256: key,
    }];
  });
}

export function deriveProjectReview(session = {}) {
  const pkg = object(session.projectPackage);
  const info = object(pkg.info);
  const gates = object(pkg.gates);
  const truth = deriveProjectTruth(session);
  const firmware = object(pkg.firmware_scaffold || object(pkg.mechatronics).firmware_scaffold);
  const mechanism = object(pkg.mechanism_pack || object(pkg.mechatronics).mechanism_pack);
  const wiring = object(pkg.wiring);
  const instructions = object(pkg.instructions);
  const revision = Number.isInteger(session.snapshotRevision) && session.snapshotRevision > 0
    ? session.snapshotRevision : null;
  const blockers = rows(gates.blockers).map((item) =>
    label(item) || label(object(item).message) || label(object(item).code)
  ).filter(Boolean);

  // A generated archive path is not proof that the ZIP is tied to this revision.
  const packageRevision = Number(info.project_revision ?? pkg.project_revision);
  const revisionBound = revision !== null && Number.isInteger(packageRevision)
    && packageRevision === revision && session.dirty !== true;

  return {
    name: label(session.projectName) || label(info.project_name) || "Untitled project",
    goal: label(session.goal) || label(info.goal),
    mode: session.mode === "salvage" ? "Reuse / donor hardware" : "New build",
    revision,
    dirty: Boolean(session.dirty),
    hasPackage: Boolean(session.projectPackage),
    parts: rows(object(pkg.bom).lines),
    wiring,
    mechanism,
    firmware,
    instructions,
    sources: sourceRows(pkg),
    blockers,
    truth,
    handoff: derivePackageHandoff(session),
    revisionBound,
    // A DRC pass is a software check, never a physical measurement.
    softwareCheck: truth.design.state === "drc_clean" ? "Checked in software"
      : truth.design.state === "drc_errors" ? "Check failed"
        : "Not checked",
    physicalCheck: "Not established by this review",
    benchSummary: truth.bench.state === "physical_authorized"
      ? "Authorization reported; inspect revision-bound bench evidence"
      : truth.bench.label,
  };
}
