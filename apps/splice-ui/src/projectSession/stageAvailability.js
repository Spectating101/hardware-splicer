/** Stage availability for the project workspace (UI gating only). */

import { STAGES, STAGE_ORDER, sessionHasBuild, sessionHasPackage } from "./projectSession.js";

export function intakeReady(session) {
  return Boolean(session?.projectId);
}

export function designReady(session) {
  // Project exists → Design is available. Home no longer bypasses Intake;
  // Verify/Bench/Package remain hard-gated on compile/package evidence.
  return Boolean(session?.projectId);
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
      return Boolean(session?.intake || sessionHasBuild(session) || session?.graph?.nodes?.length);
    case STAGES.design:
      return sessionHasBuild(session);
    case STAGES.verify:
      return sessionHasBuild(session);
    case STAGES.bench: {
      const open =
        session?.benchSession?.open_gate_count ?? (session?.benchSession?.open_gates || []).length;
      return Boolean(session?.benchSession?.power_on_authorized) || (session?.benchSession && open === 0);
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
      return "Start a project first";
    case STAGES.verify:
      return "Compile a board in Design (or finish Intake build) first";
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
  const stage = session?.currentStage || STAGES.intake;
  switch (stage) {
    case STAGES.intake:
      return {
        label: designReady(session) ? "Continue to Design" : "Describe your project above",
        stage: STAGES.design,
        enabled: designReady(session),
        primary: true,
      };
    case STAGES.design:
      return {
        label: verifyReady(session) ? "Continue to Verify" : "Compile to KiCad above",
        stage: STAGES.verify,
        enabled: verifyReady(session),
        primary: true,
      };
    case STAGES.verify:
      return {
        label: "Review bench gates",
        stage: STAGES.bench,
        enabled: benchReady(session),
        primary: true,
      };
    case STAGES.bench:
      return {
        label: "Continue to Package",
        stage: STAGES.package,
        enabled: packageReady(session),
        primary: true,
      };
    case STAGES.package:
      return {
        label: "Download or share bundle",
        stage: null,
        enabled: Boolean(session?.activeJobId),
        primary: true,
        isDownload: true,
      };
    default:
      return null;
  }
}

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

export function drcStatusFromSession(session) {
  const dq = session?.designQuality || session?.displayResult?.design_quality || {};
  const errors = dq.kicad_drc_errors;
  if (errors == null && !sessionHasBuild(session)) return { tone: "neutral", label: "Not compiled" };
  if (errors > 0) return { tone: "fail", label: `${errors} DRC error${errors === 1 ? "" : "s"}` };
  if (errors === 0) return { tone: "ok", label: "DRC clean" };
  return { tone: "neutral", label: "DRC unknown" };
}

export function benchStatusFromSession(session) {
  const bench = session?.benchSession;
  if (!bench && !sessionHasBuild(session)) return { tone: "neutral", label: "No bench yet" };
  if (bench?.power_on_authorized) return { tone: "ok", label: "Power-on authorized" };
  const open = bench?.open_gate_count ?? (bench?.open_gates || []).length;
  if (open > 0) return { tone: "warn", label: `${open} gate${open === 1 ? "" : "s"} open` };
  return { tone: "neutral", label: "Bench pending" };
}

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
