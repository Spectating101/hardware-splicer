import { useEffect, useRef, useState } from "react";
import {
  cancelDigitalJob, digitalArtifactUrl, fetchDigitalJob, fetchDigitalStudy, submitDigitalRun,
} from "./digitalStudyApi.js";
import { SavedDisplayComparison } from "./FieldDeckDisplayComparison.jsx";
import { fieldLabel } from "./digitalStudyLabels.js";
import "./digitalStudy.css";

const isPending = (status) => status === "queued" || status === "running";
const number = (value, digits = 2) => Number.isFinite(value) ? value.toFixed(digits) : "—";
const metrics = [
  ["Mass", "g", (s) => s.mass_g],
  ["Mass margin", "g", (s) => s.mass_margin_g],
  ["Payload", "g", (s) => s.requirements.payload_mass_g],
  ["Gust force scale", "×", (s) => s.requirements.gust_scale],
  ["Tracking RMS error", "mm", (s) => s.metrics.tracking_rms_m * 1000],
  ["Gust recovery error", "mm", (s) => s.metrics.gust_recovery_error_m * 1000],
  ["Peak current estimate", "A", (s) => s.metrics.peak_current_a_est],
  ["Mission charge estimate", "mAh", (s) => s.metrics.consumed_mah_est],
];

function StudyViewer({ study, label }) {
  const files = study.artifacts;
  if (!files["VIEWER.html"]) {
    const render = Object.keys(files).find((name) => /(?:^|\/)(?:assembled|device_render)\.png$/i.test(name));
    const model = Object.keys(files).find((name) => name.endsWith(".glb"));
    return <section className="digital-viewer-card">
      <h3>{label} · revision {study.revision}</h3>
      {render && <img className="digital-render" src={digitalArtifactUrl(files[render])} alt={`Assembly render for revision ${study.revision}`} />}
      {model && <p><a href={digitalArtifactUrl(files[model])}>Download 3D assembly (GLB)</a></p>}
      {!render && <p className="muted">Inspect the saved geometry in your CAD viewer.</p>}
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

export default function DigitalStudyPanel({ session, onProjectReload }) {
  const [data, setData] = useState(null);
  const [selectedRevision, setSelectedRevision] = useState(null);
  const [compareRevision, setCompareRevision] = useState(1);
  const [showPrevious, setShowPrevious] = useState(false);
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
      setSelectedRevision(result.study.revision);
      setCompareRevision(result.study.parent_revision || 1);
      const requirements = result.study.summary.requirements;
      setInputs(requirements);
      setGustScale(String(requirements.gust_scale ?? ""));
      setMassLimit(String(requirements.max_mass_g ?? ""));
      const pending = result.jobs.find((candidate) => isPending(candidate.status));
      if (pending) setJob(pending);
    }).catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [projectId, savedRevision, refresh]);

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

  const selected = data.history.find((entry) => entry.revision === selectedRevision) || data.study;
  const previous = data.history.find((entry) => entry.revision === compareRevision) || data.history.at(-1);
  const summary = selected.summary;
  const failed = summary.constraints.filter((constraint) => !constraint.passed);
  const comparing = selected.revision !== previous.revision;
  const comparisonMetrics = registered
    ? [...new Set([...Object.keys(previous.summary.metrics), ...Object.keys(summary.metrics)])].map((key) => [
      fieldLabel(key), "", (entry) => entry.metrics[key],
    ]) : metrics;
  const changedInputs = Object.entries(summary.requirements).filter(([key, value]) => previous.summary.requirements[key] !== value);
  const bom = Object.keys(selected.artifacts).find((name) => /(^|\/)bom\.csv$/i.test(name));
  const downloadable = registered ? Object.entries(selected.artifacts).filter(([name]) => name !== "STUDY.zip") : [];
  const older = selected.revision !== data.study.revision;

  return (
    <div className="digital-workshop" data-testid="digital-study">
      <header className="card digital-heading">
        <div><p className="eyebrow">Digital workshop · Revision {selected.revision}</p>
          <h1>{session.projectName}</h1><p className="muted">{selected.change_request}</p></div>
        <span className={`digital-verdict ${summary.requirements_met ? "pass" : "fail"}`}>
          {summary.requirements_met ? "Requirements passed" : "Requirements not met"}</span>
      </header>

      <div className="digital-controls card">
        <label>View revision<select value={selected.revision} onChange={(event) => setSelectedRevision(Number(event.target.value))}>
          {data.history.map((entry) => <option key={entry.revision} value={entry.revision}>
            {entry.revision} · {entry.change_request} · {entry.summary.requirements_met ? "passed" : "not met"}</option>)}
        </select></label>
        <label>Compare with<select value={previous.revision} onChange={(event) => setCompareRevision(Number(event.target.value))}>
          {data.history.map((entry) => <option key={entry.revision} value={entry.revision}>Revision {entry.revision} · {entry.change_request}</option>)}
        </select></label>
        <button type="button" onClick={() => { setError(""); setRefresh((v) => v + 1); reloadRef.current?.(projectId); }}>Reload saved project</button>
      </div>

      <div className="digital-layout">
        <div className="digital-models card">
          <StudyViewer key={selected.run_id} study={selected} label="Selected design" />
          {summary.case_id === "fielddeck-5" && <SavedDisplayComparison key={`comparison-${selected.run_id}`} study={selected} />}
          {comparing ? <>
            <button type="button" className="ghost" aria-expanded={showPrevious} onClick={() => setShowPrevious(!showPrevious)}>
              {showPrevious ? "Hide comparison design" : `Show comparison design (revision ${previous.revision})`}</button>
            {showPrevious ? <StudyViewer key={previous.run_id} study={previous} label="Comparison design" /> : null}
          </> : null}
        </div>
        <section className="card digital-change">
          <p className="eyebrow">Next revision</p><h2>Change the requirements</h2>
          {!registered && <p className="muted small">Run from revision {data.study.revision}, currently carrying {number(data.study.summary.requirements.payload_mass_g, 1)} g of study payload.</p>}
          <form onSubmit={submit}>
            {registered ? <div className="digital-field-pair">
              {Object.keys(data.study.summary.requirements).map((key) => {
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
            {older ? <p>Viewing history. <button type="button" className="ghost" onClick={() => setSelectedRevision(data.study.revision)}>Return to latest revision to run</button></p> : null}
            <button type="submit" className="primary" disabled={pending || submitting || older || !data.runtime.available}>
              {pending ? "Simulation running…" : submitting ? "Starting simulation…" : "Run and save new revision"}</button>
          </form>
          {!data.runtime.available ? <p role="status">{data.runtime.setup_hint}</p> : null}
          <div aria-live="polite" className="digital-job-status">
            {job ? <p>{isPending(job.status) ? `${job.status === "queued" ? "Queued" : "Computing"}: generating and checking this revision. You can reopen the project while it runs.`
              : job.status === "succeeded" ? "Run completed and revision saved. Review the requirements verdict and comparison below."
                : job.status === "cancelled" ? "Run cancelled. The previous revision remains saved." : "Run failed; no new design was published."}</p> : null}
            {pollError ? <p>{pollError}</p> : null}
          </div>
          {pending ? <button type="button" className="ghost" onClick={cancel}>Cancel run</button> : null}
          {error ? <p role="alert" className="digital-error">{error}</p> : null}
        </section>
      </div>

      <section className="card">
        <h2>{!comparing ? "Revision measurements" : "Before and after"}</h2>
        {comparing && <div className="digital-input-diff">
          <strong>Requirement changes from revision {previous.revision}</strong>
          {changedInputs.length ? <ul>{changedInputs.map(([key, value]) => <li key={key}>
            {fieldLabel(key)} · {previous.summary.requirements[key] ?? "—"} → {value}
          </li>)}</ul> : <p>The two revisions use the same requirements.</p>}
        </div>}
        <div className="digital-table-wrap"><table className="digital-table"><thead><tr>
          <th scope="col">Measure</th>{comparing && <th scope="col">Revision {previous.revision}</th>}<th scope="col">Revision {selected.revision}</th>{comparing && <th scope="col">Change</th>}
        </tr></thead><tbody>{comparisonMetrics.map(([label, unit, value]) => <tr key={label}>
          <th scope="row">{label}{unit && ` (${unit})`}</th>{comparing && <td>{number(value(previous.summary))}</td>}<td>{number(value(summary))}</td>
          {comparing && <td>{number(value(summary) - value(previous.summary))}</td>}</tr>)}
          {!registered && <tr><th scope="row">Centre of mass (x, y, z mm)</th>{comparing && <td>{previous.summary.centre_of_mass_mm.map((v) => number(v)).join(", ")}</td>}
            <td>{summary.centre_of_mass_mm.map((v) => number(v)).join(", ")}</td>{comparing && <td>Recomputed from mass proxies</td>}</tr>}
        </tbody></table></div>
      </section>

      <section className="card digital-evidence">
        <div><h2>{failed.length ? `${failed.length} requirement${failed.length === 1 ? "" : "s"} not met` : "Requirements passed"}</h2>
          <p>Run completed · artifact integrity verified · revision {selected.revision} saved</p>
          {failed.length ? <ul>{failed.map((constraint) => <li key={constraint.id}><strong>{constraint.label || fieldLabel(constraint.id)}</strong>
            {typeof constraint.actual === "number" && typeof constraint.limit === "number" ? `: ${number(constraint.actual)} ${constraint.unit || ""} ${registered ? "against target" : "exceeds"} ${number(constraint.limit)} ${constraint.unit || ""}` : ": check did not pass"}</li>)}</ul> : null}
          <details><summary>Inspect all {summary.constraints.length} requirement checks</summary>
            <ul>{summary.constraints.map((constraint) => <li key={constraint.id}>{constraint.passed ? "Pass" : "Fail"} · {constraint.label || fieldLabel(constraint.id)}
              {typeof constraint.actual === "number" && typeof constraint.limit === "number" ? ` · ${number(constraint.actual, 3)} / ${number(constraint.limit, 3)} ${constraint.unit || ""}` : ""}</li>)}</ul></details>
          <p className="muted small">{summary.note}</p>
        </div>
        <div><h3>Saved artifacts</h3><div className="digital-downloads">
          {(registered ? [["STUDY.zip", "Complete digital package"], [bom, "Bill of materials (CSV)"]] : [["STUDY.zip", "Complete digital package"], ["VIEWER.html", "Open standalone 3D viewer"],
            ["HS3G_B_ASSEMBLY.step", "Editable STEP"], ["HS3G_B_ASSEMBLY.glb", "3D GLB"], ["nominal.csv", "Nominal telemetry CSV"],
            ["mass_plus_5g.csv", "+5 g uncertainty CSV"], ["motor_failure.csv", "Motor failure CSV"],
            ["verification.json", "Verification receipt"]]).filter(([name]) => selected.artifacts[name]).map(([name, label]) => <a key={name}
            href={digitalArtifactUrl(selected.artifacts[name])} target={name === "VIEWER.html" ? "_blank" : undefined} rel="noreferrer">{label}</a>)}
        </div>{registered && <details><summary>Browse {downloadable.length} saved files</summary>
          <ul className="study-files">{downloadable.map(([name, url]) => <li key={name}><a href={digitalArtifactUrl(url)}>{name}</a></li>)}</ul></details>}
        <details><summary>Model assumptions and scope</summary><ul>{summary.scope_limits.map((limit) => <li key={limit}>{limit}</li>)}</ul></details></div>
      </section>
    </div>
  );
}
