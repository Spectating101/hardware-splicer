import { useEffect, useState } from "react";
import ProjectReviewPanel from "../components/ProjectReviewPanel.jsx";
import {
  assessMachineRelease, fetchMaterialAssessment, fetchPartSubstitution, fetchProjectAssurance, fetchProjectMaterials,
} from "./digitalStudyApi.js";

// Missing information stays missing. In particular, known facts never confer authority.
const value = (item, fallback = "unknown") => item === undefined || item === null || item === ""
  ? fallback : typeof item === "object" ? JSON.stringify(item) : String(item);

export default function ProjectBench({ session, study, children, references, evidenceExtra, tools, onToast, onReference }) {
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
  const revision = study?.revision ?? session.snapshotRevision;
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
  const claims = [
    ...(assurance?.claims || []),
    ...(revision === session.snapshotRevision ? session.machineProject?.requirements || [] : []).map((row) => ({ ...row, claim_id: row.requirement_id })),
    ...(study?.summary?.constraints || []),
  ];
  // These are explicit backend blocker records, never inferred from a constraint or status.
  const blockers = [...(release?.blockers || []), ...(assurance?.outputs || []).filter((row) => row.kind === "blocker")];
  const releaseExpected = Boolean(session.machineProject && revision === session.snapshotRevision);
  const blockersKnown = !evidenceError && Array.isArray(assurance?.outputs)
    && (!releaseExpected || Array.isArray(release?.blockers));
  const requirements = study?.summary?.requirements || session.constraints;
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
      <p className="muted">{revision ? `Revision ${revision}` : "Not saved yet"}{session.persistenceStatus === "saving" ? " · Saving…" : ""}</p>
      <p>Goal: {value(session.goal)}</p>
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
      <section className="bench-pane bench-design" id="bench-design" role={compact ? "tabpanel" : "region"} hidden={compact && tab !== "design"} aria-labelledby={compact ? "bench-tab-design" : "bench-design-title"}>
        <h2 id="bench-design-title">Design</h2>
        {children || <><div className="digital-mode" role="group" aria-label="Design mode">
          <button className="secondary" aria-pressed="true" type="button">Single</button>
          <button className="secondary" aria-pressed="false" type="button" disabled>Compare</button>
        </div><p>No reference study yet</p><p className="muted">Compare requires two real saved revisions.</p></>}
      </section>
      <section className="bench-pane bench-evidence" id="bench-evidence" role={compact ? "tabpanel" : "region"} hidden={compact && tab !== "evidence"} aria-labelledby={compact ? "bench-tab-evidence" : "bench-evidence-title"}>
        <h2 id="bench-evidence-title">Evidence</h2>
        {Boolean(revision) && <p>Revision {revision}</p>}
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
        {evidenceExtra}
        <ProjectReviewPanel projectId={session.projectId} currentRevision={session.snapshotRevision} onToast={onToast} disclosure />
        <div className="bench-blockers"><h3>Blockers</h3>
          {blockers.length ? <ul>{blockers.map((blocker, index) => <li key={index}>{value(typeof blocker === "string" ? blocker : blocker.message || blocker.summary)}</li>)}</ul>
            : blockersKnown ? <p>The backend returned no blockers for this revision. Revision {revision}.</p> : <p>unknown</p>}
        </div>
      </section>
    </div>
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
