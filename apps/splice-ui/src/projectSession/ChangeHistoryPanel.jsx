import { useEffect, useState } from "react";
import { VIEWS } from "../nav.js";
import { pathForRoute } from "../router";
import { describeTransition } from "./checkTransition";
import { fetchChangeDossier } from "./digitalStudyApi";
import { formatValue, keyLabel } from "./digitalStudyLabels.js";

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

const OPPOSITE = { ">=": "<", ">": "≤", "<=": ">", "<": "≥", "==": "≠" };
const SYMBOL = { ">=": "≥", "<=": "≤", "==": "=", ">": ">", "<": "<" };
const factName = (fact) => keyLabel(String(fact || "").replace(/^(metric|requirement)\./, ""));

// "Work runtime, lower estimate 3.166 h < 4 h": why a target failed, from the review's own row.
function missedTarget(target) {
  const { label, unit } = factName(target.fact);
  return `${label} ${formatValue(target.actual, unit)} ${OPPOSITE[target.operator] || "vs"} ${formatValue(target.value, unit)}`;
}

function outcomeText(outcome) {
  if (!outcome) return { text: "native outcome · not run", met: null };
  const { label, unit } = factName(outcome.fact);
  const verdict = outcome.met === true ? "meets the target" : outcome.met === false ? "misses the target" : "result unknown";
  return { text: `native outcome: ${label} ${formatValue(outcome.native_value, unit)} against ${SYMBOL[outcome.operator] || shown(outcome.operator)} ${formatValue(outcome.required, unit)}, ${verdict} (modeled, not measured)`,
    met: outcome.met };
}

// "Pi current at work load · 1 → 0.697 A", from the shared label map.
function changeText(key, before, after) {
  const { label, unit } = keyLabel(key);
  return `${label} · ${formatValue(before)} → ${formatValue(after, unit)}`;
}

// A failed check is described the way the revision compare describes it: from the base and
// applying revisions' own results, so a raised requirement is not called a design regression.
function failureText(check, baseChecks) {
  const before = (baseChecks || []).find((row) => row.id === check.id) || null;
  const { label: name } = keyLabel(check.id);
  const transition = describeTransition(before, check, "failed");
  return { name, label: transition.label, detail: transition.detail };
}

function RawValues({ change }) {
  const rows = [
    ...Object.entries(change.requirement_changes || {}).map(([key, row]) => [key, row]),
    ...(change.candidates || []).flatMap((candidate) => [[`${candidate.id}.input`, candidate.input],
      [`${candidate.id}.numbers`, candidate.numbers], [`${candidate.id}.native_outcome`, candidate.native_outcome]]),
  ];
  if (!rows.length) return null;
  return <details className="bench-raw"><summary>Machine keys and raw values</summary>
    <dl className="bench-facts">{rows.map(([key, raw]) =>
      <div key={key}><dt><code>{key}</code></dt><dd><code>{JSON.stringify(raw ?? null)}</code></dd></div>)}</dl>
  </details>;
}

// Formula inputs in words; "before" is the adjusted input's own earlier value.
function candidateInputs(candidate) {
  return Object.entries(candidate.numbers || {}).map(([key, number]) => {
    if (key === "before") return `${keyLabel(candidate.input).label}, before · ${formatValue(number, keyLabel(candidate.input).unit)}`;
    return `${keyLabel(key).label} · ${formatValue(number, keyLabel(key).unit)}`;
  });
}

function Change({ change, projectId, onOpenRevision }) {
  const applied = change.applied_revision;
  const failed = applied ? applied.checks.filter((check) => !check.passed).map((check) => failureText(check, change.base_checks)) : [];
  const missed = (change.targets || []).filter((target) => target.passed === false && target.fact);
  const candidates = change.candidates || [];
  const outcomes = candidates.map((candidate) => outcomeText(candidate.native_outcome));
  return <li className="change-entry" data-testid="change-entry">
    <p className="change-policy" data-testid="change-decision">
      Policy Lab decision on revision {change.base_revision}: <span className="change-decision">{change.policy_decision}</span>
      {missed.length > 0 && <> ({missed.map(missedTarget).join("; ")})</>}
      {candidates.length > 0 && <> · proposed modelled candidate {candidates.map((candidate) => <code key={candidate.id}>{candidate.id}</code>)}</>}
    </p>
    <p className="muted change-policy-id">Policy <code>{change.policy_id}</code> {change.policy_version}</p>
    {change.unmet?.length > 0 && <div className="change-quote"><p className="change-quote-label">Policy Lab says:</p>
      <ul>{change.unmet.map((row) => <li key={row.id}><q>{shown(row.explanation, row.id)}</q></li>)}</ul></div>}
    <dl className="change-facts">
      <div><dt>Proposal</dt><dd><ul>{Object.entries(change.requirement_changes || {}).map(([name, row]) =>
        <li key={name}>{changeText(name, row.before, row.after)}</li>)}</ul>
        {!Object.keys(change.requirement_changes || {}).length && "No requirement change stated."}</dd></div>
      <div><dt>Applied by HS</dt><dd data-testid="change-applied">{applied ? <>
        as <RevisionLink projectId={projectId} revision={applied.revision} onOpenRevision={onOpenRevision} />
        {outcomes.map((outcome, index) => <span key={index} className={outcome.met === true ? undefined : "change-failed"}> · {outcome.text}</span>)}
        {applied.requirements_met ? <span> · every modeled check passed in revision {applied.revision}</span> : failed.length
          ? failed.map((row) => <span key={row.name} className="change-failed-row">
            <span className="change-failed">{row.name}: {row.label}</span>
            {row.detail && <span className="muted"> · {row.detail}</span>}</span>)
          : <span className="change-failed"> · requirements not met</span>}
        <span className="change-failed-row muted">Record shows: HS change request <q>{shown(applied.change_request, "not recorded")}</q>
          {" · "}review check: {shown(change.review_verification, "not recorded")}</span>
      </> : "Not applied to any saved revision."}</dd></div>
      <div><dt>Change packet</dt><dd>{change.change_evidence
        ? <>sha256 <code>{short(change.change_evidence.packet_sha256)}</code></>
        : "Not exported for this change."}</dd></div>
    </dl>
    {candidates.map((candidate) => <div className="change-candidate" key={candidate.id} data-testid="change-candidate">
      <p><strong>Modelled candidate design change <code>{candidate.id}</code></strong></p>
      <p>{changeText(candidate.input, candidate.before, candidate.after)}</p>
      <p className="change-formula"><code>{shown(candidate.formula)}</code></p>
      {candidate.numbers && <ul className="change-inputs">{candidateInputs(candidate).map((text) => <li key={text}>{text}</li>)}</ul>}
      <p>Physical means of reaching this value: <strong>{candidate.physical_means}</strong></p>
    </div>)}
    <RawValues change={change} />
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
