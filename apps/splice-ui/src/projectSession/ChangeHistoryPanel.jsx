import { useEffect, useState } from "react";
import { VIEWS } from "../nav.js";
import { pathForRoute } from "../router.js";
import { fetchChangeDossier } from "./digitalStudyApi.js";

// HS's record of Policy Lab changes for this project. Every value is the backend's; the panel
// adds no judgement. Unknown and unlinked states are said in words, never implied by absence.
const shown = (item, fallback = "unknown") => item === undefined || item === null || item === "" ? fallback : String(item);
// "2026-11-20T15:14:05Z" -> "2026-11-20 15:14 UTC"; anything else is shown as recorded.
const when = (stamp) => /^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(stamp || "") ? `${stamp.slice(0, 10)} ${stamp.slice(11, 16)} UTC` : shown(stamp);
const short = (hash) => hash ? String(hash).slice(0, 16) : "unknown";

function RevisionLink({ projectId, revision, onOpenRevision }) {
  const href = pathForRoute({ view: VIEWS.workspace, projectId, revision });
  return <a href={href} onClick={(event) => {
    if (!onOpenRevision || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    onOpenRevision(revision);
  }}>revision {revision}</a>;
}

function Outcome({ outcome }) {
  if (!outcome) return <p><strong>Native outcome · not run.</strong> No saved revision applied this candidate.</p>;
  const unit = outcome.unit ? ` ${outcome.unit}` : "";
  const verdict = outcome.met === true ? "meets the target" : outcome.met === false ? "misses the target" : "unknown";
  return <p className={outcome.met === true ? undefined : "change-failed"}>
    <strong>Native outcome:</strong> {shown(outcome.fact)} = {shown(outcome.native_value)}{unit} against{" "}
    {shown(outcome.operator)} {shown(outcome.required)}{unit} · {verdict} (modeled, not measured)
  </p>;
}

function Change({ change, projectId, onOpenRevision }) {
  const applied = change.applied_revision;
  const failed = applied ? applied.checks.filter((check) => !check.passed) : [];
  return <li className="change-entry" data-testid="change-entry">
    <p className="change-policy"><span className="change-decision">{change.policy_decision}</span>{" "}
      Policy Lab <code>{change.policy_id}</code> {change.policy_version} on revision {change.base_revision}</p>
    {change.unmet?.length > 0 && <ul className="change-unmet">{change.unmet.map((row) =>
      <li key={row.id}>{shown(row.explanation, row.id)}</li>)}</ul>}
    <dl className="change-facts">
      <div><dt>Proposal</dt><dd><ul>{Object.entries(change.requirement_changes || {}).map(([name, row]) =>
        <li key={name}><code>{name}</code> {shown(row.before)} → {shown(row.after)}</li>)}</ul>
        {!Object.keys(change.requirement_changes || {}).length && "No requirement change stated."}</dd></div>
      <div><dt>Applied as</dt><dd>{applied ? <>
        <RevisionLink projectId={projectId} revision={applied.revision} onOpenRevision={onOpenRevision} />
        {applied.requirements_met ? " · every modeled check passed" : <span className="change-failed"> · failed: {failed.map((check) =>
          `${check.id} ${shown(check.actual)}${check.unit ? ` ${check.unit}` : ""} against limit ${shown(check.limit)}${check.unit ? ` ${check.unit}` : ""}`).join("; ") || "requirements not met"}</span>}
      </> : "Not applied to any saved revision."}</dd></div>
      <div><dt>Change packet</dt><dd>{change.change_evidence
        ? <>sha256 <code>{short(change.change_evidence.packet_sha256)}</code></>
        : "Not exported for this change."}</dd></div>
    </dl>
    {change.candidates.map((candidate) => <div className="change-candidate" key={candidate.id} data-testid="change-candidate">
      <p><strong>Modelled candidate design change <code>{candidate.id}</code></strong></p>
      <p><code>{candidate.input}</code> {shown(candidate.before)} → {shown(candidate.after)}</p>
      <p className="change-formula"><code>{shown(candidate.formula)}</code></p>
      {candidate.numbers && <p className="muted">Inputs: {Object.entries(candidate.numbers).map(([key, number]) => `${key} ${number}`).join(" · ")}</p>}
      <Outcome outcome={candidate.native_outcome} />
      <p>Physical means of reaching this value: <strong>{candidate.physical_means}</strong></p>
    </div>)}
  </li>;
}

function CiteState({ dossier }) {
  if (!dossier.cite_linked) return <p data-testid="cite-state"><strong>Cite dossier · not linked.</strong> HS has no recorded Cite edition for this project.</p>;
  return <ul className="change-cite" data-testid="cite-state">{dossier.cite_editions.map((edition) => {
    const check = edition.latest_check;
    return <li key={edition.edition_id}>
      <p><strong>Cite edition <code>{short(edition.edition_id)}</code></strong> · bound to revision {edition.bound_revision}
        {edition.stale_by_hs_head && <> · <span className="bench-stale">stale: HS is at revision {dossier.head_revision}</span></>}</p>
      <p className="muted">{check ? `Last currency check ${when(check.checked_at)}: ${check.status}${Number.isInteger(check.head_revision) ? ` against revision ${check.head_revision}` : ""}`
        : `Issued ${when(edition.issued_at)}; no currency check recorded.`}</p>
    </li>;
  })}</ul>;
}

export default function ChangeHistoryPanel({ projectId, latestRevision, onOpenRevision }) {
  const [dossier, setDossier] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setDossier(null); setError("");
    if (!projectId || !latestRevision) return undefined;
    const controller = new AbortController();
    Promise.resolve().then(() => fetchChangeDossier(projectId, controller.signal))
      .then((body) => {
        if (controller.signal.aborted) return;
        if (body?.change_dossier) setDossier(body.change_dossier);
        else setError("The backend returned no change history.");
      })
      .catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [projectId, latestRevision]);
  if (!projectId || !latestRevision) return null;
  return <section className="change-history" aria-labelledby="change-history-title" data-testid="change-history">
    <h3 id="change-history-title">Change history</h3>
    {error ? <p role="status">Change history · unknown. {error}</p>
      : !dossier ? <p className="muted">Loading change history…</p>
        : <>
          {dossier.changes.length ? <ol className="change-list">{dossier.changes.map((change) =>
            <Change key={change.proposal_sha256} change={change} projectId={projectId} onOpenRevision={onOpenRevision} />)}</ol>
            : <p>No Policy Lab change is recorded for this project.</p>}
          <CiteState dossier={dossier} />
          <p className="muted">Modeled values only. A recorded change grants no build, power-on or fabrication authority.</p>
        </>}
  </section>;
}
