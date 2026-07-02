import { useState } from "react";

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

function MarkdownBlock({ text }) {
  if (!text) return <p className="muted">No content.</p>;
  return <pre className="markdown-block">{text}</pre>;
}

export function InfoPanel({ pkg }) {
  const info = pkg?.info || {};
  const clarifier = info.clarifier || {};
  return (
    <div className="panel-stack">
      <section className="card">
        <h3>Project</h3>
        <p className="lead">{info.goal || "—"}</p>
        <p>{info.summary}</p>
        <dl className="meta-grid">
          <div>
            <dt>Build ID</dt>
            <dd>{info.build_id || "—"}</dd>
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
            <dt>Clarification</dt>
            <dd>{clarifier.needs_clarification ? "needed" : "clear"}</dd>
          </div>
        </dl>
      </section>
      {info.assumptions?.length > 0 && (
        <section className="card">
          <h3>Assumptions</h3>
          <ul>
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
        <h3>Bill of materials</h3>
        <span className="muted">{bom.line_count || lines.length} lines</span>
      </div>
      <div className="table-wrap">
        <table>
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
                <td className="muted">{row.source || "—"}</td>
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
          <h3>Topology operators</h3>
          <ul className="operator-list">
            {ops.map((op) => (
              <li key={op.operator_id}>
                <strong>{op.operator_id}</strong>
                <span className="muted"> ({op.operator_type})</span>
                <div className="mono small">
                  {(op.inputs || []).join(", ")} → {(op.outputs || []).join(", ")}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="card">
        <h3>Wiring guide</h3>
        <MarkdownBlock text={wiring.narrative_markdown} />
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
        <h3>Assembly steps</h3>
        <ol className="step-list">
          {steps.map((step, index) => (
            <li key={index}>
              {typeof step === "string" ? step : step.body || step.title || JSON.stringify(step)}
            </li>
          ))}
          {steps.length === 0 && <li className="muted">No assembly steps.</li>}
        </ol>
      </section>
      {instructions.bringup_markdown && (
        <section className="card">
          <h3>Bring-up</h3>
          <MarkdownBlock text={instructions.bringup_markdown} />
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
          <h3>Gate verdict</h3>
          <StatusPill
            ok={gates.power_on_authorized || gates.verdict === "POWER_ON_AUTHORIZED"}
            label={gates.verdict || "unknown"}
          />
        </div>
        <dl className="meta-grid">
          <div>
            <dt>Compile</dt>
            <dd>{gates.compile_ok ? "ok" : "blocked"}</dd>
          </div>
          <div>
            <dt>Open gates</dt>
            <dd>{gates.open_gate_count ?? items.filter((g) => g.status !== "closed").length}</dd>
          </div>
          <div>
            <dt>Power-on</dt>
            <dd>{gates.power_on_authorized ? "authorized" : "hold"}</dd>
          </div>
        </dl>
        {(gates.blockers || []).length > 0 && (
          <>
            <h4>Blockers</h4>
            <ul>
              {gates.blockers.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </>
        )}
      </section>
      <section className="card">
        <h3>Bench gates</h3>
        <ul className="gate-list">
          {items.map((gate) => (
            <li key={gate.gate_id}>
              <div className="gate-row">
                <GateBadge status={gate.status} critical={gate.critical} />
                <span className="mono small">{gate.gate_id}</span>
              </div>
              <p>{gate.prompt}</p>
            </li>
          ))}
          {items.length === 0 && <li className="muted">No bench gates yet.</li>}
        </ul>
      </section>
    </div>
  );
}

export function BenchPanel({ buildDir, benchSession, onRefresh, onSubmit }) {
  const [drafts, setDrafts] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const openGates = benchSession?.open_gates || [];

  const updateDraft = (gateId, field, value) => {
    setDrafts((prev) => ({
      ...prev,
      [gateId]: { ...(prev[gateId] || {}), [field]: value },
    }));
  };

  const handleSubmit = async (gate) => {
    const draft = drafts[gate.gate_id] || {};
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
      <section className="card">
        <p className="muted">Build a project first to open the bench session.</p>
      </section>
    );
  }

  return (
    <div className="panel-stack">
      <section className="card">
        <div className="card-header">
          <h3>Before you power on</h3>
          <button type="button" className="ghost" onClick={onRefresh}>
            Refresh
          </button>
        </div>
        <p className="muted">
          Record real measurements on the bench. Critical gates must close before power-on is authorized.
        </p>
        {benchSession && (
          <dl className="meta-grid">
            <div>
              <dt>Status</dt>
              <dd>{benchSession.level || "—"}</dd>
            </div>
            <div>
              <dt>Open gates</dt>
              <dd>{benchSession.open_gate_count ?? openGates.length}</dd>
            </div>
            <div>
              <dt>Power-on OK</dt>
              <dd>{benchSession.power_on_authorized ? "yes" : "not yet"}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="card">
        <h3>Measurements</h3>
        {openGates.length === 0 && (
          <p className="muted">All gates closed — you’re clear for the next bring-up step.</p>
        )}
        <ul className="bench-form-list">
          {openGates.map((gate) => (
            <li key={gate.gate_id} className="bench-form">
              <p>
                <GateBadge status={gate.status} critical={gate.critical} />
              </p>
              <p>{gate.prompt}</p>
              <div className="bench-inputs">
                <input
                  placeholder="Measured value"
                  value={drafts[gate.gate_id]?.value || ""}
                  onChange={(e) => updateDraft(gate.gate_id, "value", e.target.value)}
                />
                <input
                  placeholder="Unit"
                  value={drafts[gate.gate_id]?.unit || ""}
                  onChange={(e) => updateDraft(gate.gate_id, "unit", e.target.value)}
                />
                <button
                  type="button"
                  className="primary small"
                  disabled={submitting}
                  onClick={() => handleSubmit(gate)}
                >
                  Mark done
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
  { id: "bom", label: "Parts list" },
  { id: "wiring", label: "Wiring" },
  { id: "instructions", label: "Build steps" },
  { id: "gates", label: "Safety gates" },
  { id: "bench", label: "Bench" },
];
