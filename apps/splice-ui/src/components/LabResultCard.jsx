import { compileTruthHeadline, copperTierLabel, normalizeCompileTruth } from "../utils/compileTruth.js";
import { StatusPill } from "./ProjectPanels.jsx";

export default function LabResultCard({ title, subtitle, payload, error, onViewBoard, viewLabel = "View board in KiCanvas →" }) {
  if (error) {
    return (
      <div className="lab-result lab-result-fail">
        <div className="lab-result-head">
          <strong>{title}</strong>
          <StatusPill ok={false} label="Failed" />
        </div>
        <p className="error">{error}</p>
        <p className="muted small">The engine blocked or rejected this compile. Fix wiring/constraints and retry.</p>
      </div>
    );
  }

  if (!payload) return null;

  const truth = normalizeCompileTruth({ compose: payload });
  const kicadPcb = payload.artifacts?.kicad_pcb;
  const buildDir =
    payload.build_dir ||
    payload.out_dir ||
    (typeof kicadPcb === "string" ? kicadPcb.replace(/[/\\][^/\\]+$/, "") : null);
  const wireOnly = Boolean(payload.wire_only);
  const ok = wireOnly || truth.compile_ok !== false;
  const nodeCount = payload.graph?.nodes?.length;
  const wireCount = payload.graph?.wires?.length;

  return (
    <div className={`lab-result ${ok ? "lab-result-ok" : "lab-result-warn"}`}>
      <div className="lab-result-head">
        <div>
          <strong>{title}</strong>
          {subtitle && <p className="muted small">{subtitle}</p>}
        </div>
        <StatusPill ok={ok} label={wireOnly ? "Wired" : ok ? "Compiled" : "Review"} />
      </div>
      <p className="lab-result-summary">
        {wireOnly
          ? "Module graph wired through compose spine."
          : payload.mode === "llm_first"
            ? `LLM-first compose (${payload.compose_mode || "qwen"}) — ${compileTruthHeadline(truth)}`
            : compileTruthHeadline(truth)}
      </p>
      {(payload.mode === "llm_first" || payload.module_ids?.length) && (
        <dl className="lab-result-grid">
          {payload.mode && (
            <div>
              <dt>Mode</dt>
              <dd className="mono">{payload.mode}</dd>
            </div>
          )}
          {payload.module_ids?.length > 0 && (
            <div>
              <dt>Modules</dt>
              <dd className="mono small">{(payload.module_ids || []).join(", ")}</dd>
            </div>
          )}
          {payload.attempts?.length > 0 && (
            <div>
              <dt>Attempts</dt>
              <dd>{payload.attempts.length}</dd>
            </div>
          )}
        </dl>
      )}
      <dl className="lab-result-grid">
        {wireOnly ? (
          <>
            <div>
              <dt>Modules</dt>
              <dd>{nodeCount ?? "—"}</dd>
            </div>
            <div>
              <dt>Wires</dt>
              <dd>{wireCount ?? "—"}</dd>
            </div>
          </>
        ) : (
          <>
            <div>
              <dt>DRC errors</dt>
              <dd>{truth.kicad_drc_errors ?? "—"}</dd>
            </div>
            <div>
              <dt>DRC warnings</dt>
              <dd>{truth.kicad_drc_warnings ?? "—"}</dd>
            </div>
            <div>
              <dt>Copper tier</dt>
              <dd>{copperTierLabel(truth.copper_tier)}</dd>
            </div>
            <div>
              <dt>Fab note</dt>
              <dd>{truth.fab_recommendation ? String(truth.fab_recommendation).replace(/_/g, " ") : "—"}</dd>
            </div>
          </>
        )}
      </dl>
      {!wireOnly && buildDir && onViewBoard && (
        <button type="button" className="primary small" onClick={() => onViewBoard({ buildDir, truth, title })}>
          {viewLabel}
        </button>
      )}
    </div>
  );
}
