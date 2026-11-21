import { useCallback, useEffect, useState } from "react";
import ProjectReviewPanel from "../components/ProjectReviewPanel.jsx";
import ChangeHistoryPanel from "./ChangeHistoryPanel.jsx";
import DesignView, { splitGeometryNote } from "./DesignView.jsx";
import {
  assessMachineRelease, digitalArtifactUrl, engineeringPackageUrl, fetchEngineeringPackages, fetchEngineeringRevisionDiff, fetchEvidenceDelta,
  fetchMaterialAssessment, fetchPartSubstitution, fetchProjectAssurance, fetchProjectMaterials,
} from "./digitalStudyApi.js";
import { describeTransition, invalidationReason } from "./checkTransition.js";
import { factText, formatValue, keyLabel } from "./digitalStudyLabels.js";

// Missing information stays missing. In particular, known facts never confer authority.
const value = (item, fallback = "unknown") => item === undefined || item === null || item === ""
  ? fallback : typeof item === "object" ? JSON.stringify(item) : String(item);

// Which evidence a revision change invalidates is the backend's call (assurance evidence-delta).
// The bench only shows what it returns, and says "not linked" when there is nothing to ask.
function EvidenceRevisionLink({ projectId, revision, assurance, assuranceKnown, assuranceLoading = false, onSettled }) {
  const [delta, setDelta] = useState(null);
  const [error, setError] = useState("");
  const outputs = assurance?.outputs || [];
  const askable = Boolean(projectId && revision > 1 && outputs.length);
  const settled = !assuranceLoading && (!askable || Boolean(delta) || Boolean(error));
  useEffect(() => { if (settled) onSettled?.(); }, [settled, onSettled]);
  useEffect(() => {
    setDelta(null); setError("");
    if (!askable) return undefined;
    const controller = new AbortController();
    fetchEvidenceDelta(projectId, revision - 1, revision, controller.signal)
      .then((body) => { if (!controller.signal.aborted) setDelta(body); })
      .catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [projectId, revision, askable]);
  if (!projectId || !revision) return null;
  if (revision === 1) return <p className="bench-link-state">Evidence-to-revision link · revision 1 has no earlier revision to invalidate.</p>;
  if (assuranceLoading) return <p className="muted">Checking evidence against revision {revision - 1}…</p>;
  if (!askable) return <div className="bench-link-state">
    <p><strong>Evidence-to-revision link · not linked</strong></p>
    <p className="muted">{assuranceKnown
      ? `The backend assurance graph for revision ${revision} has no outputs, so it cannot report which evidence a revision change invalidated.`
      : "The assurance graph for this revision did not load, so invalidation is unknown."}</p>
  </div>;
  if (error) return <p className="bench-link-state" role="status">Evidence-to-revision link · unknown. {error}</p>;
  if (!delta) return <p className="muted">Checking evidence against revision {revision - 1}…</p>;
  const { affected_outputs: affected = [], blocked_outputs: blocked = [], retained_outputs: retained = [],
    study_checks: checks } = delta.evidence_delta || {};
  const isCheck = (row) => row.metadata?.kind === "check";
  // A check that fails now and was invalidated from the earlier revision is one result with a
  // history, not two rows: the current failure leads and the earlier result folds under it.
  const failingIds = new Set((checks?.failing_outputs || []).map((row) => row.node_id));
  const historyFor = (nodeId) => affected.find((row) => isCheck(row) && row.metadata?.node_id === nodeId);
  const staleRows = affected.filter((row) => !(isCheck(row) && failingIds.has(row.metadata?.node_id)));
  const retainedChecks = retained.filter(isCheck);
  const otherRetained = retained.length - retainedChecks.length;
  const reasons = (row) => (row.reasons || []).flatMap((reason) => reason.kind === "changed_dependency"
    ? reason.ids : reason.kind === "rerun_result_differs" ? ["the rerun result differs"]
      : reason.kind === "check_absent_in_candidate" ? ["the check is absent from the new revision"] : []);
  return <div className="bench-link-state" data-testid="evidence-delta">
    <p><strong>Changes since revision {delta.base_revision}</strong></p>
    {checks?.changed_dependencies?.length > 0 && <ul className="bench-changes">
      {checks.changed_dependencies.map((row) => <li key={row.dependency_id}>
        {row.dependency_id.startsWith("requirement:")
          ? <>Changed requirement {keyLabel(row.dependency_id.slice(12)).label}: {formatValue(row.before, keyLabel(row.dependency_id.slice(12)).unit)} → {formatValue(row.after, keyLabel(row.dependency_id.slice(12)).unit)}</>
          : <>Changed {row.dependency_id}: {value(row.before)} → {value(row.after)}</>}</li>)}
    </ul>}
    {!affected.length && !blocked.length && <p>The backend reports no invalidated outputs.</p>}
    <ul className="bench-rows">
      {staleRows.map((row) => <li key={row.evidence_id} className="is-stale" data-testid={isCheck(row) ? "stale-check" : undefined}>
        <span className="bench-stale">stale · from revision {row.metadata?.revision ?? delta.base_revision}</span>
        <strong>{checkName(row.metadata?.summary || row.evidence_id)}</strong>
        {isCheck(row) && <>
          <p>Revision {row.metadata.revision} result: {checkResult(row.metadata)} · run {String(row.metadata.run_id).slice(0, 12)}</p>
          <p>{row.metadata.rerun ? `Rerun in revision ${row.metadata.rerun.revision}: ${checkResult(row.metadata.rerun)}`
            : "No rerun of this check in the new revision."}</p>
          {reasons(row).length > 0 && <p className="muted">Invalidated by {reasons(row).join(", ")}. Kept as revision {row.metadata.revision} evidence, not counted for revision {delta.candidate_revision}.</p>}
        </>}
      </li>)}
      {blocked.map((row) => <li key={row.evidence_id}>
        <span className="bench-stale">blocked</span> <strong>{value(row.metadata?.summary || row.evidence_id)}</strong>
      </li>)}
      {retainedChecks.map((row) => <li key={row.evidence_id}>
        <span className="bench-retained">retained · from revision {row.metadata.revision}</span>
        <strong>{checkName(row.metadata.summary)}</strong>
        <p>Inputs unchanged. Rerun in revision {row.metadata.rerun?.revision} matches: {row.metadata.rerun ? checkResult(row.metadata.rerun) : "unknown"}</p>
      </li>)}
    </ul>
    {otherRetained > 0 && <p className="muted">{otherRetained} output{otherRetained === 1 ? "" : "s"} retained by the backend.</p>}
    {checks && <>
      {checks.failing_outputs?.length > 0 && <div data-testid="failing-checks">
        <p><strong>Failing in revision {checks.candidate_revision} · kept</strong></p>
        <ul className="bench-rows">{checks.failing_outputs.map((row) => {
          const history = historyFor(row.node_id);
          const change = history ? describeTransition(history.metadata, row, row.transition) : null;
          return <li key={row.node_id} className="is-failed" data-transition={change?.kind}>
            <span className="bench-failed">failed · revision {row.revision}</span> <strong>{checkName(row.summary)}</strong>
            <p>{checkResult(row)}</p>
            {change ? <p className="bench-transition"><strong>{change.label}</strong> · {change.detail}</p>
              : <p>{row.transition === "regressed" ? `Passed in revision ${checks.base_revision}` : row.transition}</p>}
            {history && <details className="bench-history" data-testid="check-history">
              <summary>Historical · invalidated by {invalidationReason(history.reasons)} · not counted for revision {delta.candidate_revision}</summary>
              <p>Revision {history.metadata.revision} result: {checkResult(history.metadata)} · run {String(history.metadata.run_id).slice(0, 12)}</p>
            </details>}
          </li>;
        })}</ul>
      </div>}
      <div data-testid="package-pair">
        <p><strong>Package before and after</strong></p>
        {["before", "after"].map((side) => {
          const pkg = checks.packages?.[side];
          return pkg?.sha256 ? <p key={side}>{side === "before" ? "Before" : "After"} · revision {pkg.revision}:{" "}
            <a href={digitalArtifactUrl(pkg.path)} download>{pkg.name}</a> · sha256 <code>{pkg.sha256.slice(0, 16)}</code></p>
            : <p key={side}><strong>Package · not linked</strong> ({side})</p>;
        })}
      </div>
    </>}
  </div>;
}

// Checks do not record their comparison direction, and minimums and maximums both occur.
// Infer it only when the result makes it unambiguous; otherwise call it a threshold.
export function thresholdLabel(row) {
  const unit = row.unit ? ` ${row.unit}` : "";
  const { actual, limit, passed } = row;
  let comparator = null;
  if (typeof actual === "number" && typeof limit === "number" && typeof passed === "boolean" && actual !== limit) {
    comparator = (actual > limit) === passed ? "≥" : "≤";
  }
  return comparator ? `required ${comparator} ${value(limit)}${unit}` : `threshold ${value(limit)}${unit}`;
}

// Check ids are machine keys; the bench names them in words and keeps the key in a tooltip.
function checkName(id) {
  return <span title={String(id)}>{keyLabel(String(id).replace(/^check:/, "")).label}</span>;
}

function checkResult(row) {
  const unit = row.unit ? ` ${row.unit}` : "";
  return `${row.passed === true ? "passed" : row.passed === false ? "failed" : "unknown"} · actual ${value(row.actual)}${unit} · ${thresholdLabel(row)}`;
}

// Stored-revision compare for non-study projects, via the engineering revision diff.
function RevisionCompare({ projectId, revision }) {
  const [state, setState] = useState(null);
  if (!projectId || !revision) return <p className="muted">Compare · needs a saved project.</p>;
  if (revision < 2) return <p className="muted">Compare · needs two saved revisions; this project has {revision}.</p>;
  async function run() {
    setState({ loading: true });
    try { setState({ body: await fetchEngineeringRevisionDiff(projectId, revision - 1, revision) }); }
    catch (cause) { setState({ error: cause.message }); }
  }
  const body = state?.body;
  return <div className="bench-compare">
    <button type="button" className="secondary" onClick={run} disabled={state?.loading}>
      Compare revision {revision - 1} → {revision}</button>
    {state?.error && <p role="status">Revision compare · unknown. {state.error}</p>}
    {body && <ul className="bench-rows">
      {[["Opened blockers", body.opened_blockers], ["Resolved blockers", body.resolved_blockers],
        ["Identity changes", body.identity_changes], ["Artifact changes", body.artifact_changes],
        ["Mechanical changes", body.mechanical_changes], ["Authority regressions", body.authority_regressions]]
        .map(([label, rows]) => <li key={label}><strong>{label}</strong>: {Array.isArray(rows) ? rows.length : "unknown"}</li>)}
    </ul>}
  </div>;
}

// What the bench can say about a revision in one glance. Counts come from backend results only;
// nothing here promotes a modeled pass to a tested one, and an empty list is never "ready".
export function summarizeRevision({ revision, studyChecks = [], blockers = [], blockersKnown, designStatus, sceneNext,
  partsKnown, evidenceKnown }) {
  const proven = studyChecks.filter((row) => row.passed === true);
  const failed = studyChecks.filter((row) => row.passed === false);
  const unknown = [];
  if (designStatus === "scene") unknown.push({ text: "Physical fit · not tested", section: "bench-design",
    next: "Test physical fit on hardware and record the result; the model shows reference geometry only" });
  if (designStatus === "records") unknown.push({ text: "Design geometry · unavailable", section: "bench-design",
    next: sceneNext || "Import the source geometry so the design can be drawn and checked" });
  if (designStatus === "not-linked") unknown.push({ text: "Design geometry · not linked", section: "bench-design",
    next: "Link design geometry: add a scene manifest for this project" });
  if (designStatus === "error") unknown.push({ text: "Design view · unknown", section: "bench-design", next: "Reload the design view" });
  if (!partsKnown) unknown.push({ text: "Parts · not recorded", section: "bench-parts", next: "Record the parts this project uses" });
  if (!evidenceKnown) unknown.push({ text: "Evidence · unknown", section: "bench-evidence", next: "Reload the evidence for this revision" });
  else if (!blockersKnown) unknown.push({ text: "Backend blockers · unknown", section: "bench-evidence", next: "Reload the release assessment" });
  const unit = (row) => (row.unit ? ` ${row.unit}` : "");
  let next;
  if (failed.length) {
    const row = failed[0];
    next = { text: `Resolve failed check ${keyLabel(row.label || row.id).label}: measured ${value(row.actual)}${unit(row)}, ${thresholdLabel(row)}`,
      source: `study run, revision ${revision}`, section: "bench-evidence" };
  } else if (blockers.length) {
    next = { text: blockers[0], source: "backend blocker", section: "bench-evidence" };
  } else if (unknown.length) {
    next = { text: unknown[0].next, source: unknown[0].text, section: unknown[0].section };
  } else {
    next = { text: `No next action can be derived for revision ${revision ?? "unsaved"}. Missing input: an engineering check or test plan for this revision.`,
      source: "nothing failing, blocked or unknown was returned", section: "bench-package", missing: true };
  }
  return { proven, failed, unknown, next };
}

function RevisionSummary({ summary, blockers, blockersKnown, studied }) {
  const { proven, failed, unknown, next } = summary;
  return <section className="bench-summary" aria-label="Revision summary" data-testid="revision-summary">
    <dl className="bench-summary-counts">
      <div data-state="proven"><dt>Proven (modeled)</dt>
        <dd><a href="#bench-evidence">{proven.length}</a> {studied ? `study check${proven.length === 1 ? "" : "s"} passed in the model, not tested` : "no modeled checks for this revision"}</dd></div>
      <div data-state="unknown"><dt>Unknown</dt>
        <dd><a href={`#${unknown[0]?.section || "bench-evidence"}`}>{unknown.length}</a> {unknown.length ? unknown.map((row) => row.text.split(" · ")[0]).join(", ") : "none listed"}</dd></div>
      <div data-state="failed" data-count={failed.length}><dt>Failed</dt>
        <dd><a href="#bench-evidence">{failed.length}</a> {failed.length ? failed.map((row) => keyLabel(row.label || row.id).label).join(", ") : studied ? "no failing study checks" : "no checks run"}</dd></div>
      <div data-state="blockers"><dt>Backend blockers</dt>
        <dd>{blockersKnown ? (blockers.length ? <><a href="#bench-evidence">{blockers.length}</a> returned</> : "none returned (not the same as passing)") : "unknown"}</dd></div>
    </dl>
    <p className="bench-summary-next" data-missing={next.missing || undefined}>
      <strong>Next action</strong> <span>{next.text}</span> <small>· {next.source}</small> <a href={`#${next.section}`}>Details</a>
    </p>
  </section>;
}

function PackagePanel({ projectId, revision, latestRevision, studyPackages, objective, blockers, blockersKnown, sceneNext, failedChecks = [],
  summaryNext = null }) {
  const [packages, setPackages] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setPackages(null); setError("");
    if (!projectId || !latestRevision) return undefined;
    const controller = new AbortController();
    fetchEngineeringPackages(projectId, controller.signal)
      .then((body) => { if (!controller.signal.aborted) setPackages(body.packages || []); })
      .catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [projectId, latestRevision]);
  const stale = (source) => Number.isInteger(source) && latestRevision && source !== latestRevision;
  const rows = [
    ...(studyPackages || []).map((row) => ({ ...row, key: `study-${row.revision}` })),
    ...(packages || []).map((row) => ({
      key: row.package_id, label: `Engineering package ${String(row.package_id).slice(0, 12)}`,
      href: engineeringPackageUrl(projectId, row.package_id), revision: row.source_revision,
    })),
  ];
  const next = [
    ...(sceneNext ? [{ text: sceneNext, source: "scene manifest" }] : []),
    ...blockers.map((text) => ({ text, source: "backend blocker" })),
    ...failedChecks.map((check) => ({
      text: `Failed check ${keyLabel(check.label || check.id).label}: actual ${value(check.actual)}${check.unit ? ` ${check.unit}` : ""}, ${thresholdLabel(check)}`,
      source: `study run, revision ${revision}`,
    })),
  ];
  return <section className="bench-package" aria-labelledby="bench-package-title" data-testid="bench-package">
    <h2 id="bench-package-title">Package and next action</h2>
    <div className="bench-package-grid">
      <div>
        <h3>Original objective</h3>
        <p>{objective || "Objective · not recorded for this project"}</p>
      </div>
      <div>
        <h3>Package</h3>
        {!projectId || !latestRevision ? <p><strong>Package · not linked</strong> (the project is not saved yet)</p> : <>
          {error && <p role="status">Engineering packages: unknown. {error}</p>}
          {rows.length ? <ul className="bench-rows">{rows.map((row) => <li key={row.key} className={stale(row.revision) ? "is-stale" : undefined}>
            <a href={row.href} download>{row.label}</a>
            <p>{stale(row.revision) ? <span className="bench-stale">stale · from revision {row.revision}</span>
              : `From revision ${value(row.revision)}`}</p>
          </li>)}</ul> : packages && <p><strong>Package · not linked</strong> No package has been built from any saved revision.</p>}
          <p className="muted">A package is a file bundle with hashes. It grants no build, power-on or fabrication authority.</p>
        </>}
      </div>
      <div>
        <h3>Next action</h3>
        {next.length ? <ol className="bench-next">{next.map((row, index) => <li key={index}>{row.text} <small className="muted">· {row.source}</small></li>)}</ol>
          // Same next action as the summary at the top, so the two never disagree.
          : summaryNext ? <p>{summaryNext.text} <small className="muted">· {summaryNext.source}</small></p>
            : blockersKnown ? <p>Next action · unknown. The backend returned no blockers and no next action for revision {revision}.</p>
              : <p>Next action · unknown</p>}
      </div>
    </div>
  </section>;
}

export default function ProjectBench({ session, study, children, references, evidenceExtra, tools, onToast, onReference,
  caseId, latestRevision, studyPackages, onOpenScene, onOpenRevision, readOnlyRevision = false }) {
  const [tab, setTab] = useState("design");
  const [compact, setCompact] = useState(() => window.matchMedia?.("(max-width: 899px)").matches ?? false);
  useEffect(() => {
    const media = window.matchMedia?.("(max-width: 899px)");
    if (!media) return;
    const update = () => setCompact(media.matches);
    update(); media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const [assurance, setAssurance] = useState(null);
  const [release, setRelease] = useState(null);
  const [materials, setMaterials] = useState(null);
  const [substitution, setSubstitution] = useState(null);
  const [evidenceError, setEvidenceError] = useState("");
  const [materialsError, setMaterialsError] = useState("");
  const [sceneManifest, setSceneManifest] = useState(null);
  const [designStatus, setDesignStatus] = useState("loading");
  // The 3D stage waits until the evidence column has settled (or 2.5 s), so its main-thread
  // geometry work cannot hold up the evidence requests and their render.
  const [evidenceSettled, setEvidenceSettled] = useState(false);
  const markEvidenceSettled = useCallback(() => setEvidenceSettled(true), []);
  useEffect(() => {
    setEvidenceSettled(false);
    const timer = setTimeout(() => setEvidenceSettled(true), 2500);
    return () => clearTimeout(timer);
  }, [session.projectId, study?.revision, session.snapshotRevision]);
  const revision = study?.revision ?? session.snapshotRevision;
  const latest = latestRevision ?? session.snapshotRevision;
  useEffect(() => {
    setAssurance(null); setRelease(null); setMaterials(null); setSubstitution(null);
    setEvidenceError(""); setMaterialsError("");
    if (!session.projectId || !revision) return;
    const controller = new AbortController();
    const { signal } = controller;
    fetchProjectAssurance(session.projectId, revision, signal).then((body) => {
      if (!signal.aborted && body.revision === revision) setAssurance(body.assurance);
    }).catch((error) => { if (!signal.aborted) setEvidenceError(error.message); });
    if (session.machineProject && revision === session.snapshotRevision) {
      assessMachineRelease(session.machineProject, signal).then((body) => {
        if (!signal.aborted) setRelease(body.assessment);
      }).catch((error) => { if (!signal.aborted) setEvidenceError(error.message); });
    }
    fetchProjectMaterials(session.projectId, signal).then(async (body) => {
      const current = body.assessments?.find((row) => row.source_revision === revision);
      if (!current || signal.aborted) return;
      const result = await fetchMaterialAssessment(session.projectId, current.assessment_id, signal);
      if (!signal.aborted && result.assessment?.source_revision === revision) setMaterials(result.assessment);
    }).catch((error) => { if (!signal.aborted) setMaterialsError(error.message); });
    if (session.partSubstitution?.assessment_id) {
      fetchPartSubstitution(session.projectId, session.partSubstitution.assessment_id, signal).then((body) => {
        if (!signal.aborted) setSubstitution(body.assessment);
      }).catch((error) => { if (!signal.aborted) setMaterialsError(error.message); });
    }
    return () => controller.abort();
  }, [session.projectId, session.snapshotRevision, session.machineProject, session.partSubstitution, revision]);

  const units = session.intake?.owned_units || [];
  const parts = session.partAssembly?.parts?.length ? session.partAssembly.parts
    : session.machineProject?.components?.length ? session.machineProject.components
      : session.intake?.available_parts || session.intake?.parts || [];
  // A study check is bound to the run that produced it; the bench names that run and revision.
  const studySource = study ? `Digital study run ${value(study.run_id)} · revision ${study.revision}` : undefined;
  const claims = [
    ...(assurance?.claims || []),
    ...(revision === session.snapshotRevision ? session.machineProject?.requirements || [] : []).map((row) => ({ ...row, claim_id: row.requirement_id })),
    ...(study?.summary?.constraints || []).map((row) => ({ ...row, source: row.source ?? studySource })),
  ];
  // These are explicit backend blocker records, never inferred from a constraint or status.
  const blockers = [...(release?.blockers || []), ...(assurance?.outputs || []).filter((row) => row.kind === "blocker")];
  const blockerText = blockers.map((blocker) => value(typeof blocker === "string" ? blocker : blocker.message || blocker.summary));
  const releaseExpected = Boolean(session.machineProject && revision === session.snapshotRevision);
  const blockersKnown = !evidenceError && Array.isArray(assurance?.outputs)
    && (!releaseExpected || Array.isArray(release?.blockers));
  const requirements = study?.summary?.requirements || session.constraints;
  const objective = session.goal || session.intake?.goal || "";
  // A failed study check is the backend's own result for this revision; it is listed, never re-judged.
  const failedChecks = (study?.summary?.constraints || []).filter((row) => row.passed === false);
  const olderRevision = Boolean(study && latest && revision !== latest);
  const partsKnown = Boolean(units.length || parts.length || materials?.inventory?.lots?.length || materials?.requirements?.length);
  const sceneNext = sceneManifest?.geometry_status === "unavailable" ? splitGeometryNote(sceneManifest.geometry_note).next : "";
  const summary = summarizeRevision({ revision, studyChecks: study?.summary?.constraints || [], blockers: blockerText, blockersKnown,
    designStatus, sceneNext, partsKnown, evidenceKnown: !evidenceError });
  const requirementSource = study ? studySource : "project intake";
  function partRow(part, kind, index) {
    const id = part.unit_id || part.part_id || part.component_id || part.material_id || part.stock_id;
    const offered = substitution?.specification?.replace_part_id === id ? [substitution.specification.candidate] : part.substitutions || [];
    return <li key={`${kind}-${id || index}`}>
      <strong>{value(part.name || part.description || part.specification || part.mpn)}</strong>
      <p>{kind} · Origin: {value(part.source || part.origin)}</p>
      <p>Knowledge state: {value(part.knowledge_state)} · Geometry: {value(part.geometry_ref, "not linked")}</p>
      <p>Catalogue part: {value(part.catalog_part_id)} · Known facts: {value(part.known_facts)}</p>
      {offered.length > 0 && <div>Offered substitutions<ul>{offered.map((offer, i) => <li key={i}>{value(offer.name || offer.part_id)} · Authority: {value(offer.authority)} · Source: {value(offer.source)}</li>)}</ul></div>}
    </li>;
  }
  return <div className="project-bench" data-testid="project-bench" data-active-pane={tab}>
    <header className="bench-heading"><h1>{session.projectName?.trim() || "Untitled project"}</h1>
      <p className="muted">{revision ? `Revision ${revision}` : "Not saved yet"}{olderRevision ? ` · the latest saved revision is ${latest}` : ""}{readOnlyRevision
        ? " · opened from a revision link, read-only; changes here are not saved" : ""}{!readOnlyRevision && session.persistenceStatus === "saving" ? " · Saving…" : ""}</p>
      {compact ? <details className="bench-objective"><summary>Objective</summary>{objective || "not recorded for this project"}</details>
        : <p className="bench-objective"><span>Objective</span> {objective || "not recorded for this project"}</p>}
    </header>
    <RevisionSummary summary={summary} blockers={blockerText} blockersKnown={blockersKnown} studied={Boolean(study)} />
    {compact && <div className="bench-tabs" role="tablist" aria-label="Project bench panes">
      {[["parts", "Parts"], ["design", "Design"], ["evidence", "Evidence"]].map(([id, label], index) => <button key={id}
        id={`bench-tab-${id}`} type="button" role="tab" aria-selected={tab === id} aria-controls={`bench-${id}`}
        tabIndex={tab === id ? 0 : -1} className="secondary" onClick={() => setTab(id)} onKeyDown={(event) => {
          const ids = ["parts", "design", "evidence"];
          const next = event.key === "ArrowRight" ? (index + 1) % 3 : event.key === "ArrowLeft" ? (index + 2) % 3
            : event.key === "Home" ? 0 : event.key === "End" ? 2 : null;
          if (next !== null) { event.preventDefault(); setTab(ids[next]); document.getElementById(`bench-tab-${ids[next]}`)?.focus(); }
        }}>{label}</button>)}
    </div>}
    <div className="bench-columns">
      <section className="bench-pane bench-design" id="bench-design" role={compact ? "tabpanel" : "region"} hidden={compact && tab !== "design"} aria-labelledby={compact ? "bench-tab-design" : "bench-design-title"}>
        <h2 id="bench-design-title">Design</h2>
        <DesignView projectId={session.projectId} caseId={caseId} revision={revision} onOpenScene={onOpenScene} onManifest={setSceneManifest}
          onStatus={setDesignStatus} holdStage={!evidenceSettled} />
        {children || <RevisionCompare projectId={session.projectId} revision={session.snapshotRevision} />}
      </section>
      <section className="bench-pane bench-parts" id="bench-parts" role={compact ? "tabpanel" : "region"} hidden={compact && tab !== "parts"} aria-labelledby={compact ? "bench-tab-parts" : "bench-parts-title"}>
        <h2 id="bench-parts-title">Parts and requirements</h2>
        {materialsError && <p role="status">Materials: unknown. {materialsError}</p>}
        {substitution && <p>Substitution assessment: {value(substitution.assessment_id)} · Source revision: {value(substitution.source_revision)} · Status: {value(substitution.report?.status)}</p>}
        <ul className="bench-rows">
          {units.map((part, index) => partRow(part, "Owned unit", index))}
          {parts.map((part, index) => partRow(part, "Project part", index))}
          {(materials?.inventory?.lots || []).map((part, index) => partRow(part, "Inventory unit", index))}
          {(materials?.requirements || []).map((part, index) => partRow(part, "Catalogue requirement", index))}
        </ul>
        {!partsKnown && <p>Parts: unknown</p>}
        <h3>Requirements</h3>
        {requirements && Object.keys(requirements).length ? <>
          <ul className="bench-requirements">{Object.entries(requirements).map(([key, fact]) =>
            <li key={key}>{factText(key, fact)}</li>)}</ul>
          <details className="bench-raw"><summary>Machine keys and raw values</summary>
            <p className="muted">Source: {requirementSource}</p>
            <dl className="bench-facts">{Object.entries(requirements).map(([key, fact]) =>
              <div key={key}><dt><code>{key}</code></dt><dd><code>{JSON.stringify(fact ?? null)}</code></dd></div>)}</dl>
          </details>
        </> : <p>unknown</p>}
      </section>
      <section className="bench-pane bench-evidence" id="bench-evidence" role={compact ? "tabpanel" : "region"} hidden={compact && tab !== "evidence"} aria-labelledby={compact ? "bench-tab-evidence" : "bench-evidence-title"}>
        <h2 id="bench-evidence-title">Evidence</h2>
        {Boolean(revision) && <p>Revision {revision}{olderRevision ? ` · superseded by revision ${latest}` : ""}</p>}
        {evidenceError && <p role="status">Evidence: unknown. {evidenceError}</p>}
        <ul className="bench-rows">{claims.map((claim, index) => <li key={claim.claim_id || claim.id || index}>
          <strong>{claim.statement || claim.label ? value(claim.statement || claim.label)
            : claim.id ? checkName(claim.id) : value(claim.predicate || claim.claim_id)}</strong>
          <p>Authority: <span>{value(claim.authority)}</span></p>
          <p>Source: {value(claim.source || claim.source_id || claim.source_ref)}</p>
          {claim.evidence_locator && <p>{value(claim.evidence_locator)}</p>}
          {Object.hasOwn(claim, "passed") && <p>Check result: {value(claim.passed)} · Actual: {value(claim.actual)} {claim.unit} · {thresholdLabel(claim)}</p>}
          {claim.value !== undefined && <p>Value: {value(claim.value)} {claim.units}</p>}
        </li>)}</ul>
        {!claims.length && <p>Claims: unknown</p>}
        {study && <p className="muted">Study scope: {value(study.summary?.note)}</p>}
        <EvidenceRevisionLink projectId={session.projectId} revision={revision} assurance={assurance}
          assuranceKnown={Boolean(assurance) && !evidenceError} assuranceLoading={!assurance && !evidenceError && Boolean(session.projectId && revision)}
          onSettled={markEvidenceSettled} />
        {evidenceExtra}
        <ChangeHistoryPanel projectId={session.projectId} latestRevision={latest} onOpenRevision={onOpenRevision} />
        <ProjectReviewPanel projectId={session.projectId} currentRevision={session.snapshotRevision} onToast={onToast} disclosure />
        <div className="bench-blockers"><h3>Blockers</h3>
          {blockers.length ? <ul>{blockerText.map((text, index) => <li key={index}>{text}</li>)}</ul>
            : blockersKnown ? <p>The backend returned no blockers for this revision. Revision {revision}.
              {failedChecks.length > 0 && ` ${failedChecks.length} study check${failedChecks.length === 1 ? "" : "s"} failed in this revision; see the checks above and Next action.`}</p>
              : <p>unknown</p>}
        </div>
      </section>
    </div>
    <PackagePanel projectId={session.projectId} revision={revision} latestRevision={latest} studyPackages={studyPackages}
      objective={objective} blockers={blockerText} blockersKnown={blockersKnown} sceneNext={sceneNext} failedChecks={failedChecks}
      summaryNext={summary.next} />
    <details className="bench-references"><summary>References</summary>
      {references || <p>Reference artifacts: unknown</p>}
      {onReference && <div className="hero-actions">
        <button className="secondary" onClick={() => onReference("reference")}>Complete CAD assembly</button>
        <button className="secondary" onClick={() => onReference("sortcell")}>Sorting workcell</button>
      </div>}
    </details>
    {tools && <details className="bench-tools"><summary>Project tools</summary>{tools}</details>}
  </div>;
}
