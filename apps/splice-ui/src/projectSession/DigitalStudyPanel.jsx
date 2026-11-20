import { useEffect, useRef, useState } from "react";
import {
  cancelDigitalJob, digitalArtifactUrl, fetchDigitalCompare, fetchDigitalJob, fetchDigitalStudy, submitDigitalRun,
} from "./digitalStudyApi.js";
import ProjectBench from "./ProjectBench.jsx";
import { SavedDisplayComparison } from "./FieldDeckDisplayComparison.jsx";
import { fieldLabel, formatValue, keyLabel } from "./digitalStudyLabels.js";
import { describeTransition } from "./checkTransition.js";
import "./digitalStudy.css";

const isPending = (status) => status === "queued" || status === "running";
const number = (value, digits = 2) => Number.isFinite(value) ? value.toFixed(digits) : "unknown";
const millimetres = (value) => Number.isFinite(value) ? value * 1000 : undefined;
const metrics = [
  ["Mass", "g", (s) => s.mass_g],
  ["Mass margin", "g", (s) => s.mass_margin_g],
  ["Payload", "g", (s) => s.requirements?.payload_mass_g],
  ["Gust force scale", "×", (s) => s.requirements?.gust_scale],
  ["Tracking RMS error", "mm", (s) => millimetres(s.metrics?.tracking_rms_m)],
  ["Gust recovery error", "mm", (s) => millimetres(s.metrics?.gust_recovery_error_m)],
  ["Peak current estimate", "A", (s) => s.metrics?.peak_current_a_est],
  ["Mission charge estimate", "mAh", (s) => s.metrics?.consumed_mah_est],
];

function StudyViewer({ study, label }) {
  const files = study.artifacts;
  if (!files["VIEWER.html"]) {
    const render = Object.keys(files).find((name) => /(?:^|\/)(?:assembled|device_render)\.png$/i.test(name));
    return <section className="digital-viewer-card">
      <h3>{label} · revision {study.revision}</h3>
      {render && <img className="digital-render" src={digitalArtifactUrl(files[render])} alt={`Assembly render for revision ${study.revision}`} />}
      {!render && <p className="muted">Geometry preview: unknown. Inspect any saved geometry using the artifact links.</p>}
    </section>;
  }
  return (
    <section className="digital-viewer-card">
      <h3>{label} · revision {study.revision}</h3>
      <iframe title={`${label} 3D assembly revision ${study.revision}`}
        src={`${digitalArtifactUrl(study.artifacts["VIEWER.html"])}?embed=1`} sandbox="allow-scripts allow-downloads" loading="lazy" />
      <p className="muted small">Drag to orbit · scroll to zoom · use Flight replay to inspect the computed path.</p>
    </section>
  );
}

// Compare reads the backend's revision comparison; the bench does not difference two summaries itself.
function RevisionComparison({ projectId, before, after }) {
  const [state, setState] = useState(null);
  useEffect(() => {
    setState(null);
    const controller = new AbortController();
    fetchDigitalCompare(projectId, before, after, controller.signal)
      .then((body) => { if (!controller.signal.aborted) setState({ body }); })
      .catch((cause) => { if (!controller.signal.aborted) setState({ error: cause.message }); });
    return () => controller.abort();
  }, [projectId, before, after]);
  if (!state) return <p className="muted">Comparing revision {before} with revision {after}…</p>;
  if (state.error) return <p role="status">Revision compare · unknown. {state.error}</p>;
  const { body } = state;
  const changes = Object.entries(body.requirements_changes || {});
  const metricRows = Object.entries(body.metrics || {});
  return <div className="digital-compare" data-testid="revision-compare">
    <div className="digital-input-diff">
      <strong>Requirement changes, revision {body.before_revision} → {body.after_revision}</strong>
      {changes.length ? <ul>{changes.map(([key, row]) => <li key={key}>
        {keyLabel(key).label} · {formatValue(row.before, keyLabel(key).unit)} → {formatValue(row.after, keyLabel(key).unit)}</li>)}</ul>
        : <p>The backend reports the same requirements in both revisions.</p>}
      <p className="muted">Engine sources: {body.same_engine_sources === true ? "same files and hashes in both revisions"
        : body.same_engine_sources === false ? "changed between the revisions" : "unknown"}</p>
    </div>
    <div className="digital-table-wrap"><table className="digital-table"><caption>Checks</caption><thead><tr>
      <th scope="col">Check</th><th scope="col">Revision {body.before_revision}</th><th scope="col">Revision {body.after_revision}</th><th scope="col">Transition</th>
    </tr></thead><tbody>{(body.constraints || []).map((row) => {
      // The label comes from the values: a limit that moved under an unchanged measurement is not a regression.
      const change = describeTransition(row.before, row.after, row.transition);
      return <tr key={row.id} data-transition={change.kind}>
        <th scope="row">{fieldLabel(row.id)}</th>
        <td>{row.before ? `${row.before.passed ? "pass" : "fail"} · ${number(row.before.actual, 3)}` : "not run"}</td>
        <td>{row.after ? `${row.after.passed ? "pass" : "fail"} · ${number(row.after.actual, 3)}` : "not run"}</td>
        <td><strong>{change.label}</strong>{change.detail && <small>{change.detail}</small>}</td></tr>;
    })}</tbody></table></div>
    <div className="digital-table-wrap"><table className="digital-table"><caption>Measurements</caption><thead><tr>
      <th scope="col">Measure</th><th scope="col">Revision {body.before_revision}</th><th scope="col">Revision {body.after_revision}</th><th scope="col">Change</th>
    </tr></thead><tbody>{metricRows.map(([key, row]) => <tr key={key}>
      <th scope="row">{fieldLabel(key)}</th>
      {["before", "after", "delta"].map((side) => <td key={side}>{Array.isArray(row[side]) ? row[side].map((v) => number(v)).join(", ") : number(row[side])}</td>)}
    </tr>)}</tbody></table></div>
  </div>;
}

export default function DigitalStudyPanel({ session, onProjectReload, onToast, onReference, onOpenScene,
  routeRevision = null, onRevisionRoute }) {
  const [data, setData] = useState(null);
  const [selectedRevision, setSelectedRevision] = useState(null);
  const [compareRevision, setCompareRevision] = useState(1);
  const [compareMode, setCompareMode] = useState(false);
  const [change, setChange] = useState("Add 10 g of payload");
  const [gustScale, setGustScale] = useState("1");
  const [massLimit, setMassLimit] = useState("250");
  const [inputs, setInputs] = useState({});
  const [job, setJob] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const reloadRef = useRef(onProjectReload);
  const routeRevisionRef = useRef(routeRevision);
  routeRevisionRef.current = routeRevision;
  const alive = useRef(true);
  const projectId = session.projectId;
  const savedRevision = session.snapshotRevision;

  useEffect(() => { reloadRef.current = onProjectReload; }, [onProjectReload]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchDigitalStudy(projectId, controller.signal).then((result) => {
      if (controller.signal.aborted) return;
      setData(result);
      // A ?rev= link opens that saved revision; an unknown one falls back to the latest and says so.
      const linked = result.history.find((row) => row.revision === routeRevisionRef.current)?.revision;
      const shown = linked ?? result.study.revision;
      setSelectedRevision(shown);
      setCompareRevision(result.history.find((row) => row.revision !== shown)?.revision ?? null);
      const requirements = result.study.summary.requirements || {};
      setInputs(requirements);
      setGustScale(String(requirements.gust_scale ?? ""));
      setMassLimit(String(requirements.max_mass_g ?? ""));
      const pending = (result.jobs || []).find((candidate) => isPending(candidate.status));
      if (pending) setJob(pending);
    }).catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [projectId, savedRevision, refresh]);

  // Back and Forward between ?rev= entries move the selection without refetching.
  useEffect(() => {
    if (!data) return;
    const linked = data.history.find((row) => row.revision === routeRevision)?.revision;
    setSelectedRevision(linked ?? data.study.revision);
  }, [data, routeRevision]);

  // One URL per view: ?rev= names an older revision only, so a link to the latest drops it.
  // An unknown revision keeps it, because the notice below explains that link.
  useEffect(() => {
    if (data && routeRevision === data.study.revision) onRevisionRoute?.(null, { replace: true });
  }, [data, routeRevision, onRevisionRoute]);

  function chooseRevision(revision) {
    setSelectedRevision(revision);
    onRevisionRoute?.(revision === data.study.revision ? null : revision);
  }

  const jobId = job?.job_id;
  const pending = isPending(job?.status);
  useEffect(() => {
    if (!jobId || !pending) return undefined;
    const controller = new AbortController();
    let timer;
    async function poll() {
      try {
        const current = await fetchDigitalJob(jobId, controller.signal);
        if (controller.signal.aborted) return;
        setJob(current);
        setPollError("");
        if (!isPending(current.status)) {
          if (current.status === "succeeded") {
            setRefresh((value) => value + 1);
            reloadRef.current?.(projectId);
          } else if (current.status === "failed") {
            setError(current.error?.message || "The run failed. The previous revision is still available.");
          }
          return;
        }
      } catch (cause) {
        if (controller.signal.aborted) return;
        setPollError(`Connection interrupted. Reconnecting to the saved job: ${cause.message}`);
      }
      timer = setTimeout(poll, 1500);
    }
    poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [jobId, pending, projectId]);

  const registered = Boolean(data?.study.summary.case_id && data.study.summary.case_id !== "hs3g-b");

  async function submit(event) {
    event.preventDefault();
    if (submitting || pending) return;
    setSubmitting(true); setError("");
    try {
      const result = await submitDigitalRun(projectId, {
        base_revision: data.study.revision, change_request: registered ? "" : change,
        requirements: registered ? Object.fromEntries(Object.entries(inputs).map(([key, value]) => [key, Number(value)])) : { gust_scale: Number(gustScale), max_mass_g: Number(massLimit) },
        request_id: crypto.randomUUID(),
      });
      if (alive.current) setJob(result.job);
    } catch (cause) {
      if (alive.current) setError(cause.message);
    } finally {
      if (alive.current) setSubmitting(false);
    }
  }

  async function cancel() {
    try {
      const result = await cancelDigitalJob(jobId);
      if (alive.current && result.job) setJob(result.job);
    } catch (cause) { if (alive.current) setError(cause.message); }
  }

  if (!data) return <section className="card" aria-busy={!error}><h2>Digital workshop</h2>
    <p role={error ? "alert" : "status"}>{error || "Opening saved geometry and simulation results…"}</p>
    {error ? <button onClick={() => { setError(""); setRefresh((v) => v + 1); }}>Retry</button> : null}</section>;

  const selected = selectedRevision === data.study.revision ? data.study
    : data.history.find((entry) => entry.revision === selectedRevision) || data.study;
  const saved = data.history.filter((entry) => Number.isInteger(entry.revision) && entry.revision > 0 && entry.run_id && entry.artifacts);
  const canCompare = new Set(saved.map((entry) => entry.revision)).size >= 2;
  const previous = saved.find((entry) => entry.revision === compareRevision && entry.revision !== selected.revision)
    || saved.find((entry) => entry.revision !== selected.revision);
  const summary = selected.summary;
  const comparing = compareMode && canCompare && Boolean(previous) && saved.some((row) => row.revision === selected.revision);
  const comparisonMetrics = registered
    ? Object.keys(summary.metrics || {}).map((key) => [fieldLabel(key), "", (entry) => entry.metrics?.[key]]) : metrics;
  const bom = Object.keys(selected.artifacts).find((name) => /(^|\/)bom\.csv$/i.test(name));
  const downloadable = registered ? Object.entries(selected.artifacts).filter(([name]) => name !== "STUDY.zip") : [];
  const older = selected.revision !== data.study.revision;
  const unknownLinkedRevision = Number.isInteger(routeRevision) && !data.history.some((row) => row.revision === routeRevision);

  const referenceLinks = <><h3>Saved artifacts</h3>{!Object.keys(selected.artifacts).length && <p>unknown</p>}<div className="digital-downloads">
    {(registered ? [["STUDY.zip", "Complete digital package"], [bom, "Bill of materials (CSV)"]] : [
      ["STUDY.zip", "Complete digital package"], ["VIEWER.html", "Open standalone 3D viewer"],
      ["HS3G_B_ASSEMBLY.step", "Editable STEP"], ["HS3G_B_ASSEMBLY.glb", "3D GLB"],
      ["nominal.csv", "Nominal telemetry CSV"], ["mass_plus_5g.csv", "+5 g uncertainty CSV"],
      ["motor_failure.csv", "Motor failure CSV"], ["verification.json", "Verification receipt"],
    ]).filter(([name]) => selected.artifacts[name]).map(([name, label]) =>
      <a key={name} href={digitalArtifactUrl(selected.artifacts[name])} target={name === "VIEWER.html" ? "_blank" : undefined} rel="noreferrer">{label}</a>)}
    </div>{registered && <details><summary>Browse {downloadable.length} saved files</summary>
      <ul className="study-files">{downloadable.map(([name, url]) => <li key={name}><a href={digitalArtifactUrl(url)}>{name}</a></li>)}</ul></details>}
    <details><summary>Model assumptions and scope</summary><ul>{(summary.scope_limits || []).map((limit) => <li key={limit}>{limit}</li>)}</ul></details></>;

  return (
    <ProjectBench session={session} study={selected} onToast={onToast} onReference={onReference} references={referenceLinks}
      caseId={summary.case_id} latestRevision={data.study.revision} onOpenScene={onOpenScene}
      studyPackages={[data.history.find((entry) => entry.revision === selected.parent_revision), selected]
        .filter((entry) => entry?.artifacts?.["STUDY.zip"]).map((entry) => ({
          label: `Digital study package (STUDY.zip) · revision ${entry.revision}`,
          href: digitalArtifactUrl(entry.artifacts["STUDY.zip"]), revision: entry.revision,
        }))}
      evidenceExtra={summary.case_id === "fielddeck-5" ? <SavedDisplayComparison key={selected.run_id} study={selected} /> : null}>
    <div className="digital-workshop" data-testid="digital-study">
      {unknownLinkedRevision && <p role="status">This link asks for revision {routeRevision}, which this project has not saved. Showing the latest saved revision, {data.study.revision}.</p>}
      {selected.change_request && <p>{selected.change_request}</p>}
      <h3 className="digital-revisions-title">Project revisions</h3>
      <div className="digital-mode" role="group" aria-label="Project revisions">
        <button className="secondary" type="button" aria-pressed={!comparing} onClick={() => setCompareMode(false)}>One revision</button>
        <button className="secondary" type="button" aria-pressed={comparing} disabled={!canCompare} onClick={() => setCompareMode(true)}>Compare revisions</button>
      </div>
      {!canCompare && <p className="muted">Compare revisions needs two real saved revisions.</p>}
      <div className="digital-controls">
        <label>View revision<select value={selected.revision} onChange={(event) => chooseRevision(Number(event.target.value))}>
          {data.history.map((entry) => <option key={entry.revision} value={entry.revision}>
            {entry.revision} · {entry.change_request}</option>)}
        </select></label>
        {comparing && <label>Compare with<select value={previous.revision} onChange={(event) => setCompareRevision(Number(event.target.value))}>
          {saved.filter((entry) => entry.revision !== selected.revision).map((entry) => <option key={entry.revision} value={entry.revision}>Revision {entry.revision} · {entry.change_request}</option>)}
        </select></label>}
        <button type="button" className="secondary" onClick={() => { setError(""); setRefresh((v) => v + 1); reloadRef.current?.(projectId); }}>Reload saved project</button>
      </div>

      <div className="digital-layout">
        <div className={`digital-models ${comparing ? "is-comparing" : ""}`}>
          <StudyViewer key={selected.run_id} study={selected} label="Selected design" />
          {comparing && <StudyViewer key={previous.run_id} study={previous} label="Comparison design" />}
        </div>
        <section className="digital-change">
          <h2>Change the requirements</h2>
          {!registered && <p className="muted small">Run from revision {data.study.revision}, currently carrying {number(data.study.summary.requirements?.payload_mass_g, 1)} g of study payload.</p>}
          <form onSubmit={submit}>
            {registered ? <div className="digital-field-pair">
              {Object.keys(data.study.summary.requirements || {}).map((key) => {
                const bounds = data.requirement_bounds?.[key];
                return <label key={key}>{fieldLabel(key)}
                  <input type="number" step="any" required min={bounds?.minimum} max={bounds?.maximum}
                    disabled={pending || submitting} value={inputs[key] ?? ""}
                    onChange={(event) => setInputs({ ...inputs, [key]: event.target.value })} />
                  {bounds && <small className="muted">{bounds.minimum} – {bounds.maximum}</small>}
                </label>;
              })}
            </div> : <><label htmlFor="digital-change">Payload change</label>
            <input id="digital-change" value={change} onChange={(event) => setChange(event.target.value)} maxLength={200}
              placeholder="Add 10 g of payload" disabled={pending || submitting} aria-describedby="digital-change-help" />
            <p id="digital-change-help" className="muted small">Add 10 g of payload · Remove 5 g of payload · Set payload to 10 g. Leave blank to change only the fields below. Payload range: 0–50 g.</p>
            <div className="digital-field-pair">
              <label>Gust force scale (×)<input type="number" min="0" max="3" step="0.1" required value={gustScale}
                onChange={(event) => setGustScale(event.target.value)} disabled={pending || submitting} /></label>
              <label>Mass limit (g)<input type="number" min="150" max="500" step="0.1" required value={massLimit}
                onChange={(event) => setMassLimit(event.target.value)} disabled={pending || submitting} /></label>
            </div>
            <p className="muted small">1× applies a [0.12, −0.08, 0] N gust for 2 seconds. This is an assumed force, not wind speed.</p></>}
            {older ? <p>Viewing history. <button type="button" className="ghost" onClick={() => chooseRevision(data.study.revision)}>Return to latest revision to run</button></p> : null}
            <button type="submit" className="primary" disabled={pending || submitting || older || !data.runtime.available}>
              {pending ? "Simulation running…" : submitting ? "Starting simulation…" : "Run and save new revision"}</button>
          </form>
          {!data.runtime.available ? <p role="status">{data.runtime.setup_hint}</p> : null}
          <div aria-live="polite" className="digital-job-status">
            {job ? <p>{isPending(job.status) ? `${job.status === "queued" ? "Queued" : "Computing"}: generating and checking this revision. You can reopen the project while it runs.`
              : job.status === "succeeded" ? "Run completed and revision saved. Review the evidence and comparison."
                : job.status === "cancelled" ? "Run cancelled. The previous revision remains saved." : "Run failed; no new design was published."}</p> : null}
            {pollError ? <p>{pollError}</p> : null}
          </div>
          {pending ? <button type="button" className="ghost" onClick={cancel}>Cancel run</button> : null}
          {error ? <p role="alert" className="digital-error">{error}</p> : null}
        </section>
      </div>

      <section>
        <h2>{!comparing ? "Revision measurements" : "Before and after"}</h2>
        {comparing ? <RevisionComparison projectId={projectId} before={previous.revision} after={selected.revision} /> : <>
          {!comparisonMetrics.length && <p>Measurements: unknown</p>}
          <div className="digital-table-wrap"><table className="digital-table"><thead><tr>
            <th scope="col">Measure</th><th scope="col">Revision {selected.revision}</th>
          </tr></thead><tbody>{comparisonMetrics.map(([label, unit, value]) => <tr key={label}>
            <th scope="row">{label}{unit && ` (${unit})`}</th><td>{number(value(summary))}</td></tr>)}
            {!registered && <tr><th scope="row">Centre of mass (x, y, z mm)</th>
              <td>{summary.centre_of_mass_mm?.map((v) => number(v)).join(", ") || "unknown"}</td></tr>}
          </tbody></table></div>
        </>}
      </section>

    </div>
    </ProjectBench>
  );
}
