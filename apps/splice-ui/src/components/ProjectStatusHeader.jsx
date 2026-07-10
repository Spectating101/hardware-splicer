import { copperHonestyLabel, drcStatusFromSession, benchStatusFromSession, evidenceLabel } from "../projectSession/stageAvailability.js";
import { STAGE_LABELS } from "../projectSession/projectSession.js";

/**
 * Compact stable project identity strip across workspace stages.
 * Hides raw build paths; surfaces honesty statuses.
 */
export default function ProjectStatusHeader({
  session,
  activeJobId,
  bundleUrl,
  onShare,
}) {
  const pkg = session.projectPackage;
  const name = session.projectName || pkg?.info?.project_name || "Untitled project";
  const goal = session.goal || pkg?.info?.goal || "";
  const mode = session.mode === "salvage" ? "Salvage" : "Greenfield";
  const stageLabel = STAGE_LABELS[session.currentStage] || session.currentStage;
  const drc = drcStatusFromSession(session);
  const bench = benchStatusFromSession(session);
  const copper = copperHonestyLabel(
    session.designQuality?.copper_tier ||
      session.displayResult?.design_quality?.copper_tier ||
      pkg?.gates?.copper_tier,
  );
  const evidence = evidenceLabel(session.benchSession, pkg);

  return (
    <header className="project-status-header" data-testid="project-status-header">
      <div className="project-status-header__identity">
        <p className="eyebrow">Active project · in-memory session</p>
        <h1 data-testid="project-status-name">{name}</h1>
        {goal ? <p className="muted project-status-header__goal">{goal}</p> : null}
      </div>

      <div className="project-status-header__chips" data-testid="project-status-chips">
        <span className="status-chip" data-testid="chip-mode">
          {mode}
        </span>
        <span className="status-chip status-chip--accent" data-testid="chip-stage">
          Stage: {stageLabel}
        </span>
        <span className={`status-chip status-chip--${drc.tone}`} data-testid="chip-drc">
          {drc.label}
        </span>
        {copper && (
          <span className={`status-chip status-chip--${copper.tone}`} data-testid="chip-copper" title={copper.detail}>
            {copper.title}
          </span>
        )}
        <span className={`status-chip status-chip--${bench.tone}`} data-testid="chip-bench">
          {bench.label}
        </span>
        {evidence && (
          <span
            className={`status-chip status-chip--${evidence.tone}`}
            data-testid="chip-evidence"
            title={evidence.detail}
          >
            {evidence.label}
          </span>
        )}
      </div>

      <div className="project-status-header__actions">
        {activeJobId && bundleUrl ? (
          <>
            <button type="button" className="ghost button-link" data-testid="share-bundle" onClick={onShare}>
              Share bundle
            </button>
            <a className="secondary button-link" href={bundleUrl} download data-testid="download-bundle">
              Download zip
            </a>
          </>
        ) : null}
      </div>
    </header>
  );
}
