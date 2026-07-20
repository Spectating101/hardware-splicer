import { useState } from "react";

import { PERSISTENCE_STATUS, projectSnapshot } from "../projectSession/projectSession.js";
import { stageMachineProjectReview } from "../projectSession/machineAuthoringApi.js";
import { projectBenchCaptureEvidence } from "../projectSession/benchCaptureEvidenceApi.js";
import "./BenchCaptureImportPanel.css";

function parseObject(value, label) {
  let parsed;
  try {
    parsed = JSON.parse(value || "{}");
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed;
}

export default function BenchCaptureImportPanel({ session, onToast }) {
  const [captureText, setCaptureText] = useState("");
  const [targetMapText, setTargetMapText] = useState("{}");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [lastReview, setLastReview] = useState(null);

  const persisted =
    session.snapshotRevision > 0 &&
    [PERSISTENCE_STATUS.saved, PERSISTENCE_STATUS.restored].includes(session.persistenceStatus);

  if (!session.machineProject) return null;

  const loadFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      setCaptureText(await file.text());
      setError("");
    } catch {
      setError("The capture file could not be read.");
    }
  };

  const submit = async () => {
    if (!persisted) {
      setError("Wait for the current revision to finish saving before importing a capture.");
      return;
    }
    try {
      const capture = parseObject(captureText, "Bench capture");
      const targetMap = parseObject(targetMapText, "Target map");
      setBusy(true);
      setError("");
      const projected = await projectBenchCaptureEvidence(
        session.machineProject,
        capture,
        targetMap,
      );
      const candidateSnapshot = {
        ...projectSnapshot(session),
        machineProject: projected.project,
      };
      const staged = await stageMachineProjectReview(session.projectId, candidateSnapshot, {
        baseRevision: session.snapshotRevision,
        createdBy: "bench-capture-importer",
        note:
          note.trim() ||
          `Import bench capture ${projected.bench_capture?.capture_id || capture.capture_id || "unknown"}`,
      });
      setResult(projected.bench_capture || null);
      setLastReview(staged.review || null);
      window.dispatchEvent(new Event("hardware-splicer:review-created"));
      onToast?.(`Bench capture staged as ${staged.review?.review_id}. Review before acceptance.`);
    } catch (err) {
      setError(err.message);
      onToast?.(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card bench-capture-import" data-testid="bench-capture-import-panel">
      <div className="bench-capture-import__header">
        <div>
          <p className="eyebrow">Bench capture bridge</p>
          <h2>Import instrument evidence without retyping it</h2>
          <p className="small muted">
            The complete capture is SHA-256 pinned. Measurements must identify an exact engineering object or use an explicit target map; prose similarity never grants authority.
          </p>
        </div>
        <span className={`bench-capture-import__state ${persisted ? "ready" : "waiting"}`}>
          {persisted ? `Based on revision ${session.snapshotRevision}` : "Waiting for saved revision"}
        </span>
      </div>

      <div className="bench-capture-import__form">
        <label className="wide">
          Capture file
          <input type="file" accept="application/json,.json" onChange={loadFile} />
        </label>
        <label className="wide">
          `bench_topology_capture.v1` JSON
          <textarea
            rows={8}
            value={captureText}
            onChange={(event) => setCaptureText(event.target.value)}
            placeholder='{"schema_version":"bench_topology_capture.v1","capture_id":"power-load-001",...}'
          />
        </label>
        <label className="wide">
          Explicit target map JSON
          <textarea
            rows={4}
            value={targetMapText}
            onChange={(event) => setTargetMapText(event.target.value)}
            placeholder='{"gate-battery":{"collection":"components","object_id":"battery"}}'
          />
        </label>
        <label className="wide">
          Proposal note
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Which bench run this was and what changed"
          />
        </label>
      </div>

      {error && <p className="bench-capture-import__error" role="alert">{error}</p>}

      {result && (
        <div className="bench-capture-import__result" data-testid="bench-capture-import-result">
          <span><strong>{result.imported_count}</strong> imported</span>
          <span><strong>{result.measurement_count}</strong> measurement rows</span>
          <span><strong>{result.warnings?.length || 0}</strong> warnings</span>
          <code>{result.capture_sha256}</code>
          {(result.warnings || []).map((warning) => (
            <p key={`${warning.code}-${warning.measurement || warning.message}`}>
              <strong>{warning.code.replaceAll("_", " ")}</strong> — {warning.message}
            </p>
          ))}
        </div>
      )}

      {lastReview && (
        <p className="small muted" data-testid="bench-capture-staged">
          Staged {lastReview.review_id} against revision {lastReview.base_revision}. Imported evidence has not changed the project yet.
        </p>
      )}

      <div className="bench-capture-import__actions">
        <button
          type="button"
          className="primary"
          disabled={busy || !persisted || !captureText.trim()}
          onClick={submit}
        >
          Stage capture evidence
        </button>
      </div>
    </section>
  );
}
