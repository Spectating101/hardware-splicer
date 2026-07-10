import { agentStepLabel, bumpDrcFixup } from "./studioDrc.js";

function severityClass(severity) {
  return String(severity || "").toLowerCase() === "error" ? "studio-drc-violation--error" : "studio-drc-violation--warn";
}

export default function StudioDrcPanel({
  drc,
  agentSteps,
  compiling,
  onAutoFix,
  onOpenProject,
  onDismiss,
}) {
  if (!drc && !compiling) return null;

  const errors = drc?.truth?.kicad_drc_errors ?? 0;
  const warnings = drc?.truth?.kicad_drc_warnings ?? 0;
  const clean = errors === 0;
  const canAutoFix = drc && !clean && !compiling;
  const nextFixup = drc?.fixup ? bumpDrcFixup(drc.fixup) : bumpDrcFixup();

  return (
    <aside className="studio-drc card">
      <header className="studio-drc__header">
        <div>
          <p className="eyebrow">Design check</p>
          <h2>{compiling ? "Compiling…" : drc?.headline || "KiCad DRC feedback"}</h2>
        </div>
        {drc && (
          <span className={`studio-drc__badge ${clean ? "ok" : "fail"}`}>
            {clean ? "DRC clean" : `${errors} error${errors === 1 ? "" : "s"}`}
          </span>
        )}
      </header>

      {agentSteps?.length > 0 && (
        <ol className="studio-drc__steps">
          {agentSteps.map((step) => (
            <li key={step.id} className={`studio-drc__step studio-drc__step--${step.status}`}>
              <span className="studio-drc__step-dot" aria-hidden />
              <div>
                <strong>{agentStepLabel(step.id)}</strong>
                {step.detail && <span className="muted small">{step.detail}</span>}
              </div>
            </li>
          ))}
        </ol>
      )}

      {drc?.moduleIds?.length > 0 && (
        <div className="studio-drc__meta">
          <h3>Modules picked</h3>
          <p className="mono small">{drc.moduleIds.join(", ")}</p>
          {drc.composeMode && (
            <p className="muted small">
              Design path: <span className="mono">{drc.composeMode}</span>
              {drc.mode ? ` · ${drc.mode}` : ""}
            </p>
          )}
          {drc.hasPackage && (
            <p className="hint small">Project package ready — continue to Verify for preview and gates.</p>
          )}
        </div>
      )}

      {drc?.agentRounds?.length > 0 && (
        <div className="studio-drc__loop">
          <h3>Agent rounds</h3>
          <ul className="studio-drc__attempts">
            {drc.agentRounds.map((row) => (
              <li key={`agent-round-${row.round}`}>
                <span className="mono small">r{row.round}</span>
                <span>
                  {row.kicad_drc_errors} error(s), {row.kicad_drc_warnings} warning(s)
                </span>
                {row.violation_types?.length > 0 && (
                  <span className="chip small">{row.violation_types.join(", ")}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {drc?.attempts?.length > 0 && (
        <div className="studio-drc__loop">
          <h3>KiCad fix loop</h3>
          <ul className="studio-drc__attempts">
            {drc.attempts.map((row) => (
              <li key={row.attempt}>
                <span className="mono small">#{row.attempt + 1}</span>
                <span>
                  {row.kicad_drc_errors} error(s), {row.kicad_drc_warnings} warning(s)
                </span>
                {row.fix_buckets?.length > 0 && (
                  <span className="chip small">{row.fix_buckets.join(", ")}</span>
                )}
              </li>
            ))}
          </ul>
          {drc.resolved && <p className="hint small ok-text">Engine auto-fix resolved DRC before handoff.</p>}
        </div>
      )}

      {drc?.violations?.length > 0 && (
        <div className="studio-drc__violations">
          <h3>Remaining violations</h3>
          <ul>
            {drc.violations.slice(0, 8).map((row, idx) => (
              <li key={`${row.type}-${idx}`} className={`studio-drc-violation ${severityClass(row.severity)}`}>
                <span className="mono small">{row.type || "violation"}</span>
                <span>{row.description || row.message || "KiCad DRC error"}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!compiling && drc && (
        <div className="studio-drc__summary muted small">
          <span>{warnings} warning(s)</span>
          {drc.truth?.copper_tier && <span> · {String(drc.truth.copper_tier).replace(/_/g, " ")}</span>}
        </div>
      )}

      {!compiling && drc?.resolved && drc.copperTier && String(drc.copperTier).includes("cosmetic") && (
        <p className="hint small" data-testid="studio-copper-honesty">
          KiCad DRC errors are clear, but copper is still a <strong>preview layout</strong>
          {drc.fabRecommendation ? ` (${drc.fabRecommendation})` : ""}. That is not fabrication-ready.
        </p>
      )}

      <div className="studio-drc__actions">
        {canAutoFix && (
          <button type="button" className="secondary" onClick={() => onAutoFix(nextFixup)}>
            Auto-fix &amp; recompile
          </button>
        )}
        {drc?.outDir && (
          <button type="button" className="primary" data-testid="continue-to-verify" onClick={() => onOpenProject(drc)}>
            Continue to Verify
          </button>
        )}
        {drc && (
          <button type="button" className="ghost" onClick={onDismiss}>
            Dismiss
          </button>
        )}
      </div>

      {canAutoFix && (
        <p className="hint small">
          Applies extra geometry spacing ({Object.entries(nextFixup).map(([k, v]) => `${k}=${v}`).join(", ")}) and
          re-runs KiCad compile + DRC.
        </p>
      )}
    </aside>
  );
}
