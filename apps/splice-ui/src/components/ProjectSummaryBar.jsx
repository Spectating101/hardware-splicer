import { GateBadge, StatusPill } from "./ProjectPanels.jsx";

export default function ProjectSummaryBar({ pkg, benchSession, onGoBench, onGoDesign }) {
  const gates = pkg?.gates || {};
  const openCount =
    benchSession?.open_gate_count ??
    gates.open_gate_count ??
    (benchSession?.open_gates || []).length;
  const total =
    (benchSession?.gates || []).length ||
    openCount + (benchSession?.closed_gates || []).length ||
    0;
  const closed = total > 0 ? total - openCount : 0;
  const pct = total > 0 ? Math.round((closed / total) * 100) : 0;
  const verdict = gates.verdict || "UNKNOWN";
  const powerOk = gates.power_on_authorized || benchSession?.power_on_authorized;

  return (
    <section className={`summary-bar ${powerOk ? "summary-ok" : "summary-hold"}`}>
      <div className="summary-verdict">
        <span className="summary-label">Gate verdict</span>
        <StatusPill ok={powerOk} label={verdict.replace(/_/g, " ")} />
      </div>
      <div className="summary-progress">
        <div className="summary-progress-head">
          <span>Bench gates</span>
          <span className="mono">
            {closed}/{total || "—"} closed
          </span>
        </div>
        <div className="progress-track" aria-hidden>
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className="summary-stats">
        <div className="summary-stat">
          <span className="summary-stat-label">Compile</span>
          <span>{gates.compile_ok ? "DRC pass" : "review"}</span>
        </div>
        <div className="summary-stat">
          <span className="summary-stat-label">Critical open</span>
          <span>{gates.critical_open_count ?? "—"}</span>
        </div>
        <div className="summary-stat">
          <span className="summary-stat-label">Power-on</span>
          <span>
            <GateBadge status={powerOk ? "closed" : "open"} critical={!powerOk} />
            {powerOk ? " OK" : " hold"}
          </span>
        </div>
      </div>
      {openCount > 0 && onGoBench && (
        <button type="button" className="primary small summary-cta" onClick={onGoBench}>
          Close {openCount} gate{openCount === 1 ? "" : "s"} on bench →
        </button>
      )}
      {onGoDesign && (
        <button type="button" className="secondary small summary-cta" onClick={onGoDesign}>
          View KiCad board →
        </button>
      )}
    </section>
  );
}
