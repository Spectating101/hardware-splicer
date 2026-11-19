import { lazy, Suspense, useEffect, useState } from "react";
import { fetchSceneManifest, fetchSceneRecords, fetchScenes } from "../api.js";
import { sceneRevisions } from "../components/sceneRevisions.js";

const FieldDeckScene = lazy(() => import("../components/FieldDeckScene.jsx"));
const SCENE_SCHEMA = "hardware_splicer.scene_manifest.v1";

// A bench project reaches a scene only through data: the manifest's own project_id, or a
// registered study case the manifest declares. Titles and names are never compared.
export function matchScene(scenes, { projectId, caseId }) {
  const rows = Array.isArray(scenes) ? scenes : [];
  const byId = projectId ? rows.find((row) => row.project_id === projectId) : undefined;
  if (byId) return { scene: byId, via: "project id" };
  const byCase = caseId ? rows.find((row) => row.registered_cases?.includes(caseId)) : undefined;
  return byCase ? { scene: byCase, via: `registered case ${caseId}` } : null;
}

// geometry_note carries the source status on its first line and the next required action after it.
export function splitGeometryNote(note) {
  const text = typeof note === "string" ? note : "";
  const index = text.indexOf("\n");
  return index < 0 ? { status: text.trim(), next: "" } : { status: text.slice(0, index).trim(), next: text.slice(index + 1).trim() };
}

const scalar = (value) => value === null || ["string", "number", "boolean"].includes(typeof value);
const shown = (value) => value === null ? "null" : String(value);

function GeometryRecords({ manifest }) {
  const [records, setRecords] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetchSceneRecords(manifest.project_id, controller.signal)
      .then((body) => { if (!controller.signal.aborted) setRecords(body.records || []); })
      .catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [manifest.project_id]);
  const { status, next } = splitGeometryNote(manifest.geometry_note);
  const hashed = (manifest.sources || []).filter((row) => row.sha256);
  // A recorded false flag is work that has not been done; it is listed, never answered.
  const questions = (records || []).flatMap((record) => Object.entries(record.data || {})
    .filter(([, value]) => value === false).map(([field]) => ({ field, path: record.path })));
  return <div className="design-records">
    <h3>{manifest.geometry_label || "Design"} geometry unavailable · {status || "unknown"}</h3>
    <p className="muted">No 3D stage is drawn: this project has no importable geometry yet.</p>
    <dl className="bench-facts">
      {hashed.map((row) => <div key={row.sha256}>
        <dt>Source</dt>
        <dd>{row.href ? <a href={row.href} target="_blank" rel="noreferrer">{row.label}</a> : row.label}</dd>
        <dt>sha256</dt><dd className="mono">{row.sha256}</dd>
      </div>)}
      {!hashed.length && <div><dt>Source</dt><dd>unknown</dd></div>}
      <div><dt>Next required action</dt><dd>{next || "unknown"}</dd></div>
    </dl>
    <h4>Parts</h4>
    <ul className="design-record-list">
      {(manifest.revisions || []).map((row) => <li key={row.id}>
        {manifest.title} · {manifest.subtitle || "role unknown"} · {row.label || row.id} · parts sidecar: {row.parts ? row.parts : "not linked"}
      </li>)}
    </ul>
    <h4>Open questions</h4>
    {error && <p role="status">Records: unknown. {error}</p>}
    {!error && !records && <p className="muted">Loading records…</p>}
    {records && !questions.length && <p>None recorded as false in the listed records.</p>}
    {questions.length > 0 && <ol className="design-record-list">
      {questions.map(({ field, path }) => <li key={`${path}:${field}`}><code>{field}</code> · false · {path}</li>)}
    </ol>}
    {(records || []).map((record) => <details key={record.path}><summary>{record.label || record.path} · {record.status}</summary>
      {record.data && <dl className="bench-facts">{Object.entries(record.data).filter(([, value]) => scalar(value)).map(([key, value]) =>
        <div key={key}><dt>{key}</dt><dd>{shown(value)}</dd></div>)}</dl>}
    </details>)}
  </div>;
}

export default function DesignView({ projectId, caseId, revision, onOpenScene, onManifest }) {
  const [state, setState] = useState({ status: "loading" });
  useEffect(() => { onManifest?.(state.status === "linked" ? state.manifest : null); }, [state, onManifest]);
  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    setState({ status: "loading" });
    fetchScenes(signal).then(async (scenes) => {
      const match = matchScene(scenes, { projectId, caseId });
      if (!match) { if (!signal.aborted) setState({ status: "not-linked" }); return; }
      const manifest = await fetchSceneManifest(match.scene.project_id, signal);
      if (signal.aborted) return;
      if (manifest?.schema !== SCENE_SCHEMA) setState({ status: "error", error: "Scene manifest schema is not recognised." });
      else setState({ status: "linked", manifest, via: match.via });
    }).catch((cause) => { if (!signal.aborted) setState({ status: "error", error: cause.message }); });
    return () => controller.abort();
  }, [projectId, caseId]);

  if (state.status === "loading") return <div className="design-view" data-design-state="loading"><p className="muted">Loading design view…</p></div>;
  if (state.status === "error") return <div className="design-view" data-design-state="error">
    <p><strong>Design view · unknown</strong></p><p role="status">{state.error}</p></div>;
  if (state.status === "not-linked") return <div className="design-view" data-design-state="not-linked">
    <p><strong>Design view · not linked</strong></p>
    <p className="muted">A scene manifest (<code>projects/&lt;folder&gt;/scene.json</code>, schema <code>{SCENE_SCHEMA}</code>) whose
      {" "}<code>project_id</code> is <code>{projectId || "this project's id"}</code>
      {caseId ? <> or whose <code>registered_cases</code> lists <code>{caseId}</code></> : null} would link this project to a design view.</p>
  </div>;

  const { manifest, via } = state;
  const drawable = manifest.geometry_status === "available" && sceneRevisions(manifest).length > 0;
  return <div className="design-view" data-design-state={drawable ? "scene" : "records"}>
    <div className="design-view-source">
      <p className="muted">Scene <code>projects/{manifest.project_id}/scene.json</code> · linked by {via}. {drawable
        ? `Reference geometry from the repository${revision ? `, not generated by revision ${revision} of this project` : ""}.`
        : "Geometry source records from the repository."}</p>
      {drawable && onOpenScene && <button type="button" className="ghost" onClick={() => onOpenScene({ projectId: manifest.project_id, manifest })}>
        Open full screen</button>}
    </div>
    {drawable ? <Suspense fallback={<p className="muted">Loading 3D scene…</p>}>
      <FieldDeckScene projectId={manifest.project_id} manifest={manifest} embedded />
    </Suspense> : <GeometryRecords manifest={manifest} />}
  </div>;
}
