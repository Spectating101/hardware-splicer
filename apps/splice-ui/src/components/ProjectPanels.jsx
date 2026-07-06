import { useState } from "react";
import MarkdownView from "./MarkdownView.jsx";

export function StatusPill({ ok, label }) {
  return <span className={`status-pill ${ok ? "ok" : "warn"}`}>{label}</span>;
}

export function GateBadge({ status, critical }) {
  const cls = status === "closed" ? "closed" : status === "blocked" ? "blocked" : "open";
  return (
    <span className={`gate-badge ${cls}`}>
      {status || "open"}
      {critical ? " · critical" : ""}
    </span>
  );
}

export function InfoPanel({ pkg }) {
  const info = pkg?.info || {};
  const clarifier = info.clarifier || {};
  return (
    <div className="panel-stack">
      <section className="card">
        <h3>Project overview</h3>
        <p className="lead">{info.goal || "—"}</p>
        <p className="summary-text">{info.summary}</p>
        <dl className="meta-grid">
          <div>
            <dt>Build ID</dt>
            <dd className="mono">{info.build_id || "—"}</dd>
          </div>
          <div>
            <dt>Archetype</dt>
            <dd>{info.archetype || "—"}</dd>
          </div>
          <div>
            <dt>Est. cost</dt>
            <dd>{info.cost_estimate_usd != null ? `$${info.cost_estimate_usd}` : "—"}</dd>
          </div>
          <div>
            <dt>Intent</dt>
            <dd>{clarifier.needs_clarification ? "needs clarification" : "clear"}</dd>
          </div>
        </dl>
      </section>
      {info.assumptions?.length > 0 && (
        <section className="card">
          <h3>Assumptions</h3>
          <ul className="clean-list">
            {info.assumptions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export function BomPanel({ pkg }) {
  const bom = pkg?.bom || {};
  const lines = bom.lines || [];
  return (
    <section className="card">
      <div className="card-header">
        <h3>Parts list</h3>
        <span className="chip">{bom.line_count || lines.length} lines</span>
      </div>
      {bom.estimated_total_usd != null && (
        <p className="bom-total">
          Estimated total: <strong>${bom.estimated_total_usd}</strong>
        </p>
      )}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Ref</th>
              <th>Description</th>
              <th>Qty</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((row, index) => (
              <tr key={`${row.ref || row.module_id}-${index}`}>
                <td className="mono">{row.ref || row.module_id || "—"}</td>
                <td>{row.description || row.module_id || "—"}</td>
                <td>{row.qty ?? 1}</td>
                <td>
                  <span className="chip muted-chip">{row.source || "—"}</span>
                </td>
              </tr>
            ))}
            {lines.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  No BOM lines in package.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function WiringPanel({ pkg }) {
  const wiring = pkg?.wiring || {};
  const ops = wiring.topology_operators || [];
  return (
    <div className="panel-stack">
      {ops.length > 0 && (
        <section className="card">
          <h3>Topology</h3>
          <div className="operator-grid">
            {ops.map((op) => (
              <article key={op.operator_id} className="operator-card">
                <header>
                  <strong className="mono">{op.operator_id}</strong>
                  <span className="chip">{op.operator_type}</span>
                </header>
                <p className="mono small flow-line">
                  {(op.inputs || []).join(", ") || "—"} → {(op.outputs || []).join(", ") || "—"}
                </p>
              </article>
            ))}
          </div>
        </section>
      )}
      <section className="card">
        <h3>Wiring guide</h3>
        <MarkdownView text={wiring.narrative_markdown} />
      </section>
    </div>
  );
}

export function InstructionsPanel({ pkg }) {
  const instructions = pkg?.instructions || {};
  const steps = instructions.assembly_steps || [];
  return (
    <div className="panel-stack">
      <section className="card">
        <h3>Build steps</h3>
        <ol className="step-cards">
          {steps.map((step, index) => (
            <li key={index}>
              <span className="step-num">{index + 1}</span>
              <div>
                {typeof step === "string"
                  ? step
                  : step.body || step.title || JSON.stringify(step)}
              </div>
            </li>
          ))}
          {steps.length === 0 && <li className="muted">No assembly steps.</li>}
        </ol>
      </section>
      {instructions.bringup_markdown && (
        <section className="card">
          <h3>Bring-up notes</h3>
          <MarkdownView text={instructions.bringup_markdown} />
        </section>
      )}
    </div>
  );
}

export function GatesPanel({ pkg, benchSession }) {
  const gates = pkg?.gates || {};
  const items = benchSession?.gates || [];
  return (
    <div className="panel-stack">
      <section className="card">
        <div className="card-header">
          <h3>Safety gate verdict</h3>
          <StatusPill
            ok={gates.power_on_authorized || gates.verdict === "POWER_ON_AUTHORIZED"}
            label={(gates.verdict || "unknown").replace(/_/g, " ")}
          />
        </div>
        {(gates.blockers || []).length > 0 && (
          <div className="blocker-box">
            <h4>Blockers</h4>
            <ul>
              {gates.blockers.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </section>
      <section className="card">
        <h3>All gates ({items.length})</h3>
        <div className="gate-card-grid">
          {items.map((gate) => (
            <article
              key={gate.gate_id}
              className={`gate-card ${gate.status === "closed" ? "gate-closed" : "gate-open"}`}
            >
              <header>
                <GateBadge status={gate.status} critical={gate.critical} />
                <span className="mono small">{gate.gate_id}</span>
              </header>
              <p>{gate.prompt}</p>
              {gate.measurement?.value != null && (
                <p className="measurement-line mono small">
                  ✓ {gate.measurement.value}
                  {gate.measurement.unit ? ` ${gate.measurement.unit}` : ""}
                </p>
              )}
            </article>
          ))}
          {items.length === 0 && <p className="muted">No bench gates in session.</p>}
        </div>
      </section>
    </div>
  );
}

export function BenchPanel({ buildDir, benchSession, onRefresh, onSubmit, onSuccess }) {
  const [drafts, setDrafts] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [lastClosed, setLastClosed] = useState(null);
  const openGates = benchSession?.open_gates || [];

  const updateDraft = (gateId, field, value) => {
    setDrafts((prev) => ({
      ...prev,
      [gateId]: { ...(prev[gateId] || {}), [field]: value },
    }));
  };

  const handleSubmit = async (gate) => {
    const draft = drafts[gate.gate_id] || {};
    if (!draft.value?.trim()) return;
    setSubmitting(true);
    try {
      await onSubmit([
        {
          gate_id: gate.gate_id,
          value: draft.value,
          unit: draft.unit,
          notes: draft.notes,
          status: "closed",
        },
      ]);
      setLastClosed(gate.gate_id);
      onSuccess?.(`Gate ${gate.gate_id} closed`);
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[gate.gate_id];
        return next;
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (!buildDir) {
    return (
      <section className="card empty-card">
        <p className="muted">Build a project first to open the bench session.</p>
      </section>
    );
  }

  return (
    <div className="panel-stack">
      <section className="card bench-hero">
        <div className="card-header">
          <div>
            <h3>Bench — before power-on</h3>
            <p className="muted">Record real measurements. Critical gates must close first.</p>
          </div>
          <button type="button" className="ghost" onClick={onRefresh}>
            Refresh
          </button>
        </div>
        {benchSession && (
          <dl className="meta-grid">
            <div>
              <dt>Status</dt>
              <dd>{benchSession.level || "—"}</dd>
            </div>
            <div>
              <dt>Open</dt>
              <dd>{benchSession.open_gate_count ?? openGates.length}</dd>
            </div>
            <div>
              <dt>Power-on</dt>
              <dd>{benchSession.power_on_authorized ? "Authorized" : "Hold"}</dd>
            </div>
          </dl>
        )}
        {lastClosed && <p className="success small">Last closed: {lastClosed}</p>}
      </section>

      <section className="card">
        <h3>Open measurements ({openGates.length})</h3>
        {openGates.length === 0 && (
          <div className="success-box">
            <strong>All gates closed</strong>
            <p>Review gate verdict before energizing the harness.</p>
          </div>
        )}
        <ul className="bench-form-list">
          {openGates.map((gate) => (
            <li key={gate.gate_id} className={`bench-form ${gate.critical ? "critical" : ""}`}>
              <header>
                <GateBadge status={gate.status} critical={gate.critical} />
                {gate.critical && <span className="critical-tag">Must measure</span>}
              </header>
              <p>{gate.prompt}</p>
              <div className="bench-inputs">
                <input
                  placeholder="Measured value (e.g. 5.02)"
                  value={drafts[gate.gate_id]?.value || ""}
                  onChange={(e) => updateDraft(gate.gate_id, "value", e.target.value)}
                />
                <input
                  placeholder="Unit (V, Ω, …)"
                  value={drafts[gate.gate_id]?.unit || ""}
                  onChange={(e) => updateDraft(gate.gate_id, "unit", e.target.value)}
                />
                <button
                  type="button"
                  className="primary"
                  disabled={submitting || !drafts[gate.gate_id]?.value?.trim()}
                  onClick={() => handleSubmit(gate)}
                >
                  Close gate
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export const PROJECT_TABS = [
  { id: "info", label: "Overview" },
  { id: "design", label: "Design" },
  { id: "bom", label: "Parts" },
  { id: "wiring", label: "Wiring" },
  { id: "instructions", label: "Build" },
  { id: "gates", label: "Gates" },
  { id: "bench", label: "Bench" },
];
