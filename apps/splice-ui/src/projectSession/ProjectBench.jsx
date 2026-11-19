import { useEffect, useState } from "react";
import ProjectReviewPanel from "../components/ProjectReviewPanel.jsx";
import DesignView, { splitGeometryNote } from "./DesignView.jsx";
import {
  assessMachineRelease, engineeringPackageUrl, fetchEngineeringPackages, fetchEngineeringRevisionDiff, fetchEvidenceDelta,
  fetchMaterialAssessment, fetchPartSubstitution, fetchProjectAssurance, fetchProjectMaterials,
} from "./digitalStudyApi.js";

// Missing information stays missing. In particular, known facts never confer authority.
const value = (item, fallback = "unknown") => item === undefined || item === null || item === ""
  ? fallback : typeof item === "object" ? JSON.stringify(item) : String(item);

// Which evidence a revision change invalidates is the backend's call (assurance evidence-delta).
// The bench only shows what it returns, and says "not linked" when there is nothing to ask.
function EvidenceRevisionLink({ projectId, revision, assurance, assuranceKnown }) {
  const [delta, setDelta] = useState(null);
  const [error, setError] = useState("");
  const outputs = assurance?.outputs || [];
  const askable = Boolean(projectId && revision > 1 && outputs.length);
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
  if (!askable) return <div className="bench-link-state">
    <p><strong>Evidence-to-revision link · not linked</strong></p>
    <p className="muted">{assuranceKnown
      ? `The backend assurance graph for revision ${revision} has no outputs, so it cannot report which evidence a revision change invalidated.`
      : "The assurance graph for this revision did not load, so invalidation is unknown."}</p>
  </div>;
  if (error) return <p className="bench-link-state" role="status">Evidence-to-revision link · unknown. {error}</p>;
  if (!delta) return <p className="muted">Checking evidence against revision {revision - 1}…</p>;
  const { affected_outputs: affected = [], blocked_outputs: blocked = [], retained_outputs: retained = [] } = delta.evidence_delta || {};
  return <div className="bench-link-state" data-testid="evidence-delta">
    <p><strong>Changes since revision {delta.base_revision}</strong></p>
    {!affected.length && !blocked.length && <p>The backend reports no invalidated outputs.</p>}
    <ul className="bench-rows">
      {affected.map((row) => <li key={row.evidence_id} className="is-stale">
        <span className="bench-stale">stale · from revision {delta.base_revision}</span>
        <strong>{value(row.metadata?.summary || row.evidence_id)}</strong>
      </li>)}
      {blocked.map((row) => <li key={row.evidence_id}>
        <span className="bench-stale">blocked</span> <strong>{value(row.metadata?.summary || row.evidence_id)}</strong>
      </li>)}
    </ul>
    {retained.length > 0 && <p className="muted">{retained.length} output{retained.length === 1 ? "" : "s"} retained by the backend.</p>}
  </div>;
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

function PackagePanel({ projectId, revision, latestRevision, studyPackages, objective, blockers, blockersKnown, sceneNext, failedChecks = [] }) {
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
      text: `Failed check ${value(check.label || check.id)}: actual ${value(check.actual)}${check.unit ? ` ${check.unit}` : ""}, limit ${value(check.limit)}${check.unit ? ` ${check.unit}` : ""}`,
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
          : blockersKnown ? <p>Next action · unknown. The backend returned no blockers and no next action for revision {revision}.</p>
            : <p>Next action · unknown</p>}
      </div>
    </div>
  </section>;
}

export default function ProjectBench({ session, study, children, references, evidenceExtra, tools, onToast, onReference,
  caseId, latestRevision, studyPackages, onOpenScene }) {
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
  const sceneNext = sceneManifest?.geometry_status === "unavailable" ? splitGeometryNote(sceneManifest.geometry_note).next : "";
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
      <p className="muted">{revision ? `Revision ${revision}` : "Not saved yet"}{olderRevision ? ` · the latest saved revision is ${latest}` : ""}{session.persistenceStatus === "saving" ? " · Saving…" : ""}</p>
      <p className="bench-objective"><span>Objective</span> {objective || "not recorded for this project"}</p>
    </header>
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
        <DesignView projectId={session.projectId} caseId={caseId} revision={revision} onOpenScene={onOpenScene} onManifest={setSceneManifest} />
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
        {!units.length && !parts.length && !materials?.inventory?.lots?.length && !materials?.requirements?.length && <p>Parts: unknown</p>}
        <h3>Requirements</h3>
        {requirements && Object.keys(requirements).length ? <dl className="bench-facts">{Object.entries(requirements).map(([key, fact]) =>
          <div key={key}><dt>{key}</dt><dd>{value(fact)}</dd></div>)}</dl> : <p>unknown</p>}
      </section>
      <section className="bench-pane bench-evidence" id="bench-evidence" role={compact ? "tabpanel" : "region"} hidden={compact && tab !== "evidence"} aria-labelledby={compact ? "bench-tab-evidence" : "bench-evidence-title"}>
        <h2 id="bench-evidence-title">Evidence</h2>
        {Boolean(revision) && <p>Revision {revision}{olderRevision ? ` · superseded by revision ${latest}` : ""}</p>}
        {evidenceError && <p role="status">Evidence: unknown. {evidenceError}</p>}
        <ul className="bench-rows">{claims.map((claim, index) => <li key={claim.claim_id || claim.id || index}>
          <strong>{value(claim.statement || claim.label || claim.predicate || claim.claim_id || claim.id)}</strong>
          <p>Authority: <span>{value(claim.authority)}</span></p>
          <p>Source: {value(claim.source || claim.source_id || claim.source_ref)}</p>
          {claim.evidence_locator && <p>{value(claim.evidence_locator)}</p>}
          {Object.hasOwn(claim, "passed") && <p>Check result: {value(claim.passed)} · Actual: {value(claim.actual)} · Limit: {value(claim.limit)} {claim.unit}</p>}
          {claim.value !== undefined && <p>Value: {value(claim.value)} {claim.units}</p>}
        </li>)}</ul>
        {!claims.length && <p>Claims: unknown</p>}
        {study && <p className="muted">Study scope: {value(study.summary?.note)}</p>}
        <EvidenceRevisionLink projectId={session.projectId} revision={revision} assurance={assurance}
          assuranceKnown={Boolean(assurance) && !evidenceError} />
        {evidenceExtra}
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
      objective={objective} blockers={blockerText} blockersKnown={blockersKnown} sceneNext={sceneNext} failedChecks={failedChecks} />
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
