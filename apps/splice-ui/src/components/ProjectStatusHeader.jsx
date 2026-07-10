import { deriveProjectTruth } from "../projectSession/deriveProjectTruth.js";
import { STAGE_LABELS } from "../projectSession/projectSession.js";
import { jobBundleUrl } from "../api.js";

/**
 * Compact stable project identity strip — chips from deriveProjectTruth only.
 */
export default function ProjectStatusHeader({ session, activeJobId, onShare }) {
  const truth = deriveProjectTruth(session);
  const pkg = session.projectPackage;
  const name = session.projectName || pkg?.info?.project_name || "Untitled project";
  const goal = session.goal || pkg?.info?.goal || "";
  const mode = session.mode === "salvage" ? "Salvage" : "Greenfield";
  const stageLabel = STAGE_LABELS[session.currentStage] || session.currentStage;
  const bundleUrl = activeJobId ? jobBundleUrl(activeJobId) : null;

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
        <span
          className={`status-chip status-chip--${chipTone(truth.design.state)}`}
          data-testid="chip-drc"
        >
          {truth.design.label}
        </span>
        {truth.copper.state !== "not_available" && (
          <span
            className={`status-chip status-chip--${truth.copper.state === "preview_only" ? "warn" : "neutral"}`}
            data-testid="chip-copper"
            title={truth.copper.detail}
          >
            {truth.copper.label}
          </span>
        )}
        <span
          className={`status-chip status-chip--${benchTone(truth.bench.state)}`}
          data-testid="chip-bench"
        >
          {truth.bench.label}
        </span>
        {truth.bench.simulated && (
          <span className="status-chip status-chip--warn" data-testid="chip-evidence">
            Simulated evidence
          </span>
        )}
        {truth.bench.physical && truth.bench.powerOnAuthorized && !truth.bench.simulated && (
          <span className="status-chip status-chip--ok" data-testid="chip-evidence">
            Physical evidence
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

function chipTone(designState) {
  if (designState === "drc_clean") return "ok";
  if (designState === "drc_errors") return "fail";
  return "neutral";
}

function benchTone(state) {
  if (state === "physical_authorized") return "ok";
  if (state === "simulated_pass" || state === "gates_open") return "warn";
  return "neutral";
}
