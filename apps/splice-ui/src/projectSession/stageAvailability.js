/** Stage availability for the project workspace (UI gating only). */

import { STAGES, STAGE_ORDER, sessionHasBuild, sessionHasPackage } from "./projectSession.js";
import { deriveProjectTruth } from "./deriveProjectTruth.js";

export function intakeReady(session) {
  return Boolean(session?.projectId);
}

export function designReady(session) {
  if (!session?.projectId) return false;
  if (!session.intakeComplete) return false;
  // Non-editable recent builds still open Design to show a bounded explanation
  // (not a fake blank canvas). Editable Studio requires designEditable !== false.
  return true;
}

export function verifyReady(session) {
  return sessionHasBuild(session);
}

export function benchReady(session) {
  return sessionHasBuild(session);
}

export function packageReady(session) {
  return sessionHasPackage(session);
}

const CHECKERS = {
  [STAGES.intake]: intakeReady,
  [STAGES.design]: designReady,
  [STAGES.verify]: verifyReady,
  [STAGES.bench]: benchReady,
  [STAGES.package]: packageReady,
};

export function stageIsAvailable(session, stageId) {
  const check = CHECKERS[stageId];
  return check ? check(session) : false;
}

export function stageIsComplete(session, stageId) {
  switch (stageId) {
    case STAGES.intake:
      return Boolean(session?.intakeComplete);
    case STAGES.design:
      return sessionHasBuild(session);
    case STAGES.verify:
      return sessionHasBuild(session);
    case STAGES.bench: {
      const truth = deriveProjectTruth(session);
      return truth.bench.state === "physical_authorized" || truth.bench.state === "simulated_pass";
    }
    case STAGES.package:
      return sessionHasPackage(session);
    default:
      return false;
  }
}

export function stageBlockReason(session, stageId) {
  if (stageIsAvailable(session, stageId)) return null;
  switch (stageId) {
    case STAGES.intake:
      return "Start a project first";
    case STAGES.design:
      if (!session?.intakeComplete) return "Finish Intake before Design";
      return "Design not available";
    case STAGES.verify:
      return "Compile a board in Design (or finish salvage build) first";
    case STAGES.bench:
      return "Needs a compiled board before gates";
    case STAGES.package:
      return "Package appears after a successful build";
    default:
      return "Not available yet";
  }
}

export function buildStageTabs(session) {
  return STAGE_ORDER.map((id) => ({
    id,
    label: ({
      [STAGES.intake]: "Intake",
      [STAGES.design]: "Design",
      [STAGES.verify]: "Verify",
      [STAGES.bench]: "Bench",
      [STAGES.package]: "Package",
    })[id],
    available: stageIsAvailable(session, id),
    complete: stageIsComplete(session, id),
    blockedReason: stageBlockReason(session, id),
    highlight: id === STAGES.design || id === STAGES.verify,
  }));
}

export function nextStageAction(session) {
  const truth = deriveProjectTruth(session);
  const stage = session?.currentStage || STAGES.intake;
  if (stage === STAGES.intake) {
    return null; // wizard owns CTA
  }
  if (stage === STAGES.design) {
    return {
      label: verifyReady(session) ? "Continue to Verify" : "Compile to KiCad above",
      stage: STAGES.verify,
      enabled: verifyReady(session),
      primary: true,
    };
  }
  if (stage === STAGES.verify) {
    return {
      label: "Review bench gates",
      stage: STAGES.bench,
      enabled: benchReady(session),
      primary: true,
    };
  }
  if (stage === STAGES.bench) {
    return {
      label: "Continue to Package",
      stage: STAGES.package,
      enabled: packageReady(session),
      primary: true,
    };
  }
  if (stage === STAGES.package) {
    return {
      label: "Download or share bundle",
      stage: null,
      enabled: Boolean(session?.activeJobId),
      primary: true,
      isDownload: true,
    };
  }
  return {
    label: truth.overall.nextAction.label,
    stage: truth.overall.nextAction.stage,
    enabled: stageIsAvailable(session, truth.overall.nextAction.stage),
    primary: true,
  };
}

/** @deprecated Prefer deriveProjectTruth(session).copper — kept for thin honesty helpers/tests */
export function copperHonestyLabel(tier) {
  if (!tier) return null;
  const raw = String(tier);
  if (raw.includes("cosmetic") || raw.includes("preview")) {
    return {
      tone: "warn",
      title: "Copper preview only",
      detail: "KiCad DRC may be clean, but routing is not fabrication-ready.",
    };
  }
  if (raw.includes("autorout") || raw.includes("fab")) {
    return {
      tone: "ok",
      title: "Copper review",
      detail: String(tier).replace(/_/g, " "),
    };
  }
  return {
    tone: "neutral",
    title: "Copper status",
    detail: String(tier).replace(/_/g, " "),
  };
}

/** @deprecated Prefer deriveProjectTruth(session).bench */
export function evidenceLabel(benchSession, pkg) {
  const simulated =
    benchSession?.simulated === true ||
    benchSession?.evidence_kind === "simulated" ||
    pkg?.gates?.simulated === true ||
    String(benchSession?.source || "").includes("simulat");
  if (simulated) {
    return { tone: "warn", label: "Simulated evidence", detail: "Not physical café measurement" };
  }
  if (benchSession?.power_on_authorized || (benchSession?.open_gate_count === 0 && benchSession)) {
    const physical =
      benchSession?.evidence_kind === "physical" ||
      benchSession?.simulated === false ||
      pkg?.gates?.simulated === false;
    if (physical) {
      return { tone: "ok", label: "Physical evidence", detail: "Operator/capture path" };
    }
  }
  return null;
}

export { deriveProjectTruth };
