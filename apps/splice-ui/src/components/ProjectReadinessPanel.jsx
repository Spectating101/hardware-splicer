import { deriveEvidenceTruth, evidenceTone } from "../projectSession/deriveEvidenceTruth.js";
import { deriveProjectTruth } from "../projectSession/deriveProjectTruth.js";

/** Compact readiness panel driven by shared truth models — one story, one next action. */
export default function ProjectReadinessPanel({ session, onGoStage }) {
  const truth = deriveProjectTruth(session);
  const evidence = deriveEvidenceTruth(session);
  const hold = truth.overall.state !== "authorized" || (evidence.applicable && !evidence.powerAuthorized);

  return (
    <section
      className={`project-readiness-panel ${hold ? "readiness-hold" : "readiness-ok"}`}
      data-testid="project-readiness-panel"
    >
      <div className="project-readiness-panel__main">
        <p className="eyebrow">Project readiness</p>
        <h2 data-testid="readiness-headline">
          {evidence.applicable && evidence.state === "blocked" ? evidence.label : truth.overall.headline}
        </h2>
        <div className="project-readiness-panel__dims">
          {evidence.applicable && (
            <span
              className={`status-chip status-chip--${evidenceTone(evidence.state)}`}
              data-testid="ready-evidence"
              title={evidence.detail}
            >
              Evidence: {evidence.label}
            </span>
          )}
          <span className={`status-chip status-chip--${toneForDesign(truth.design.state)}`} data-testid="ready-design">
            Design: {truth.design.label}
          </span>
          <span className={`status-chip status-chip--${toneForCopper(truth.copper.state)}`} data-testid="ready-copper">
            {truth.copper.label}
          </span>
          <span className={`status-chip status-chip--${toneForBench(truth.bench.state)}`} data-testid="ready-bench">
            Bench: {truth.bench.label}
          </span>
        </div>
        {evidence.applicable && evidence.state === "blocked" && (
          <p className="small muted" data-testid="readiness-evidence-note">
            {evidence.detail} Open Verify to inspect the exact donor-interface blockers before using generated firmware.
          </p>
        )}
        {truth.copper.state === "preview_only" && <p className="small muted" data-testid="readiness-copper-note">{truth.copper.detail}</p>}
        {truth.bench.simulated && <p className="small muted" data-testid="readiness-sim-note">Simulated evidence is not physical café proof.</p>}
      </div>
      {truth.overall.nextAction?.stage && onGoStage && (
        <button type="button" className="primary" data-testid="readiness-next" onClick={() => onGoStage(truth.overall.nextAction.stage)}>
          {truth.overall.nextAction.label}
        </button>
      )}
    </section>
  );
}

function toneForDesign(state) {
  if (state === "drc_clean") return "ok";
  if (state === "drc_errors") return "fail";
  return "neutral";
}

function toneForCopper(state) {
  if (state === "preview_only" || state === "review_required") return "warn";
  if (state === "fab_candidate") return "ok";
  return "neutral";
}

function toneForBench(state) {
  if (state === "physical_authorized") return "ok";
  if (state === "simulated_pass" || state === "gates_open" || state === "authorization_pending") return "warn";
  return "neutral";
}
