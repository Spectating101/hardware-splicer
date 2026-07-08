import { useCallback, useEffect, useMemo, useState } from "react";
import { benchCaptureTemplate } from "../api.js";
import { GateBadge, StatusPill } from "./ProjectPanels.jsx";

const PASS_STATUSES = new Set(["pass", "passed", "ok", "verified", "closed"]);

function defaultDraft(row) {
  return {
    value: row.value != null ? String(row.value) : "",
    unit: row.unit || (row.kind === "voltage" ? "V" : row.kind === "current" ? "A" : ""),
    status: row.status && PASS_STATUSES.has(String(row.status).toLowerCase()) ? "pass" : "pass",
    notes: row.notes || "",
  };
}

export default function BenchCapturePanel({ buildDir, benchSession, onSubmitCapture, onRefresh, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [template, setTemplate] = useState(null);
  const [operatorId, setOperatorId] = useState("bench_operator");
  const [instrumentId, setInstrumentId] = useState("bench_dmm_01");
  const [drafts, setDrafts] = useState({});
  const [benchPhoto, setBenchPhoto] = useState(null);

  const openMeasurements = useMemo(() => {
    const rows = template?.measurements || [];
    return rows.filter((row) => String(row.status || "open") !== "closed");
  }, [template]);

  const loadTemplate = useCallback(async () => {
    if (!buildDir) return;
    setLoading(true);
    setError("");
    try {
      const payload = await benchCaptureTemplate(buildDir);
      const tpl = payload.template || payload;
      setTemplate(tpl);
      const nextDrafts = {};
      for (const row of tpl.measurements || []) {
        if (row.gate_id) nextDrafts[row.gate_id] = defaultDraft(row);
      }
      setDrafts(nextDrafts);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [buildDir]);

  useEffect(() => {
    loadTemplate();
  }, [loadTemplate]);

  const updateDraft = (gateId, field, value) => {
    setDrafts((prev) => ({
      ...prev,
      [gateId]: { ...(prev[gateId] || {}), [field]: value },
    }));
  };

  const handlePhoto = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setBenchPhoto({ name: file.name, dataUrl: String(reader.result || "") });
    };
    reader.readAsDataURL(file);
  };

  const buildCapturePacket = () => {
    const measurements = openMeasurements.map((row) => {
      const draft = drafts[row.gate_id] || defaultDraft(row);
      return {
        gate_id: row.gate_id,
        kind: row.kind || "voltage",
        target: row.target || row.notes || row.gate_id,
        value: draft.value,
        unit: draft.unit,
        status: draft.status || "pass",
        instrument_id: instrumentId,
        operator_id: operatorId,
        notes: draft.notes || row.notes || "",
      };
    });
    const artifacts = (template?.artifacts || []).map((row) => ({ ...row }));
    if (benchPhoto?.dataUrl) {
      artifacts.push({
        kind: "photo",
        uri: benchPhoto.dataUrl,
        notes: benchPhoto.name || "Bench capture photo",
      });
    }
    return {
      schema_version: "bench_topology_capture.v1",
      capture_id: template?.capture_id || "ui_bench_capture",
      project_name: template?.project_name || benchSession?.project_name || "",
      build_id: template?.build_id || benchSession?.build_id || "",
      operator_id: operatorId,
      instrument_id: instrumentId,
      recorded_at: new Date().toISOString(),
      instruments: template?.instruments || [
        { instrument_id: instrumentId, instrument_type: "calibrated_dmm", calibration_status: "valid" },
      ],
      measurements,
      artifacts,
      policy: template?.policy,
    };
  };

  const handleSubmitCapture = async () => {
    const filled = openMeasurements.filter((row) => drafts[row.gate_id]?.value?.trim());
    if (filled.length === 0) {
      setError("Enter at least one measurement value before submitting capture.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const capture = buildCapturePacket();
      const result = await onSubmitCapture(capture);
      if (!result?.ok) {
        throw new Error(result?.error || "Capture did not close any gates");
      }
      onSuccess?.(`Capture closed ${result.mapped_count || 0} gate(s)`);
      await loadTemplate();
      await onRefresh?.();
      setBenchPhoto(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (!buildDir) return null;

  return (
    <section className="card bench-capture-card">
      <div className="card-header">
        <div>
          <h3>Bench capture packet</h3>
          <p className="muted small">
            Structured <code>bench_topology_capture.v1</code> — instrument readings + optional bench photo. Closes
            matching gates in one submit.
          </p>
        </div>
        <button type="button" className="ghost small" onClick={loadTemplate} disabled={loading}>
          {loading ? "Loading…" : "Reload template"}
        </button>
      </div>

      <div className="field-grid">
        <div className="field-block">
          <label className="field-label" htmlFor="bench-operator">
            Operator ID
          </label>
          <input id="bench-operator" value={operatorId} onChange={(e) => setOperatorId(e.target.value)} />
        </div>
        <div className="field-block">
          <label className="field-label" htmlFor="bench-instrument">
            Instrument ID
          </label>
          <input id="bench-instrument" value={instrumentId} onChange={(e) => setInstrumentId(e.target.value)} />
        </div>
      </div>

      {openMeasurements.length === 0 ? (
        <div className="success-box">
          <strong>All capture slots filled or no open gates</strong>
          <p className="muted small">Use per-gate entry below or build a project with bench gates first.</p>
        </div>
      ) : (
        <ul className="bench-capture-list">
          {openMeasurements.map((row) => (
            <li key={row.gate_id} className="bench-capture-row">
              <header>
                <GateBadge status="open" critical={Boolean(row.critical)} />
                <span className="mono small">{row.gate_id}</span>
                <span className="chip small">{row.kind}</span>
              </header>
              <p>{row.target || row.notes}</p>
              <div className="bench-inputs">
                <input
                  placeholder="Value"
                  value={drafts[row.gate_id]?.value || ""}
                  onChange={(e) => updateDraft(row.gate_id, "value", e.target.value)}
                />
                <input
                  placeholder="Unit"
                  value={drafts[row.gate_id]?.unit || ""}
                  onChange={(e) => updateDraft(row.gate_id, "unit", e.target.value)}
                />
                <select
                  value={drafts[row.gate_id]?.status || "pass"}
                  onChange={(e) => updateDraft(row.gate_id, "status", e.target.value)}
                >
                  <option value="pass">pass</option>
                  <option value="fail">fail</option>
                  <option value="open">open / hold</option>
                </select>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="ai-upload-block">
        <label className="field-label" htmlFor="bench-capture-photo">
          Bench photo (optional evidence)
        </label>
        <input id="bench-capture-photo" type="file" accept="image/*" onChange={(e) => handlePhoto(e.target.files?.[0])} />
        {benchPhoto?.dataUrl && (
          <div className="ai-photo-preview">
            <img src={benchPhoto.dataUrl} alt="Bench capture" />
            <span className="muted small">{benchPhoto.name}</span>
          </div>
        )}
      </div>

      <div className="ai-action-row">
        <button
          type="button"
          className="primary"
          disabled={submitting || openMeasurements.length === 0}
          onClick={handleSubmitCapture}
        >
          {submitting ? "Submitting capture…" : "Submit bench capture packet"}
        </button>
        <StatusPill
          ok={(benchSession?.open_gate_count ?? 0) === 0}
          label={`${benchSession?.open_gate_count ?? 0} gates open`}
        />
      </div>

      {error && <p className="error">{error}</p>}
      {template?.template_path && (
        <p className="hint small mono">Template: {template.template_path}</p>
      )}
    </section>
  );
}
