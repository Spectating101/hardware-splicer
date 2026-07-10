/**
 * Single multidimensional project truth model.
 *
 * Source precedence (documented):
 * Design/DRC:
 *   1. designQuality.kicad_drc_errors
 *   2. compose/agent-loop DRC truth
 *   3. package.gates compile evidence (only when explicit)
 *   4. unknown — missing compile_ok is NOT success
 * Bench:
 *   1. benchSession
 *   2. package.gates snapshot
 *   3. not started
 * Evidence: simulated and physical stay separate.
 * Copper: copper_tier honesty boundary.
 */

import { sessionHasBuild, sessionHasPackage, STAGES } from "./projectSession.js";

function pick(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return null;
}

function numOrNull(value) {
  if (value === undefined || value === null || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function deriveProjectTruth(session = {}) {
  const pkg = session.projectPackage || {};
  const gates = pkg.gates || {};
  const dq = session.designQuality || session.displayResult?.design_quality || {};
  const agent = session.agentLoop || session.composeResult?.agent_loop || {};
  const bench = session.benchSession || session.displayResult?.bench_session || null;

  const errors = numOrNull(
    pick(dq.kicad_drc_errors, dq.drc_errors, agent.final_kicad_drc_errors, gates.kicad_drc_errors),
  );
  const warnings = numOrNull(pick(dq.kicad_drc_warnings, dq.drc_warnings, gates.kicad_drc_warnings));

  let designState = "not_compiled";
  if (!sessionHasBuild(session)) {
    designState = "not_compiled";
  } else if (errors == null && gates.compile_ok !== true && gates.compile_ok !== false) {
    // Explicit: missing compile_ok must not become success
    designState = "unknown";
  } else if (errors != null && errors > 0) {
    designState = "drc_errors";
  } else if (errors === 0 || gates.compile_ok === true) {
    designState = "drc_clean";
  } else if (gates.compile_ok === false) {
    designState = "drc_errors";
  } else {
    designState = "unknown";
  }

  const copperTier = pick(dq.copper_tier, gates.copper_tier, agent.copper_tier);
  let copperState = "not_available";
  let copperLabel = "Copper not assessed";
  let copperDetail = "";
  if (copperTier) {
    const raw = String(copperTier);
    if (raw.includes("cosmetic") || raw.includes("preview")) {
      copperState = "preview_only";
      copperLabel = "Copper preview only";
      copperDetail = "DRC-clean does not mean fabrication-ready.";
    } else if (raw.includes("review")) {
      copperState = "review_required";
      copperLabel = "Copper review required";
      copperDetail = raw.replace(/_/g, " ");
    } else if (raw.includes("fab") || raw.includes("autoroute")) {
      copperState = "fab_candidate";
      copperLabel = "Copper fab candidate";
      copperDetail = raw.replace(/_/g, " ");
    } else {
      copperState = "review_required";
      copperLabel = "Copper status";
      copperDetail = raw.replace(/_/g, " ");
    }
  }

  const openGateCount = numOrNull(
    pick(bench?.open_gate_count, gates.open_gate_count, (bench?.open_gates || []).length),
  );
  const criticalOpenCount = numOrNull(pick(bench?.critical_open_count, gates.critical_open_count)) || 0;
  const powerOnAuthorized = Boolean(pick(bench?.power_on_authorized, gates.power_on_authorized));
  const simulated = Boolean(
    bench?.simulated === true ||
      bench?.evidence_kind === "simulated" ||
      gates.simulated === true ||
      String(bench?.source || "").includes("simulat"),
  );
  const physical = Boolean(
    bench?.evidence_kind === "physical" ||
      bench?.simulated === false ||
      gates.simulated === false,
  );

  let benchState = "not_started";
  if (!bench && !sessionHasBuild(session)) {
    benchState = "not_started";
  } else if (powerOnAuthorized && physical && !simulated) {
    benchState = "physical_authorized";
  } else if (powerOnAuthorized && simulated) {
    benchState = "simulated_pass";
  } else if ((openGateCount ?? 0) > 0 || criticalOpenCount > 0) {
    benchState = "gates_open";
  } else if (bench || gates.open_gate_count != null) {
    benchState = simulated ? "simulated_pass" : "gates_open";
  }

  const packageState = sessionHasPackage(session) ? "generated" : "missing";

  let overallState = "needs_design";
  let headline = "Complete Intake, then design the board";
  let nextAction = { label: "Continue Intake", stage: STAGES.intake };

  if (!session.intakeComplete) {
    overallState = "needs_design";
    headline = "Finish Intake to unlock Design";
    nextAction = { label: "Continue Intake", stage: STAGES.intake };
  } else if (!sessionHasBuild(session)) {
    overallState = "needs_design";
    headline = "Design and compile the board";
    nextAction = { label: "Open Design", stage: STAGES.design };
  } else if (designState === "drc_errors" || designState === "unknown") {
    overallState = "needs_verification";
    headline = "Review design verification before handoff";
    nextAction = { label: "Open Verify", stage: STAGES.verify };
  } else if (benchState === "gates_open" || benchState === "not_started") {
    overallState = "power_on_blocked";
    headline = "Close bench gates before power-on";
    nextAction = { label: "Review Bench", stage: STAGES.bench };
  } else if (benchState === "simulated_pass") {
    overallState = "review_required";
    headline = "Simulated bench pass — not physical authorization";
    nextAction = { label: "Review Package", stage: STAGES.package };
  } else if (copperState === "preview_only") {
    overallState = "review_required";
    headline = "Design clean · Copper preview only · Not fabrication-ready";
    nextAction = { label: "Review Package", stage: STAGES.package };
  } else if (benchState === "physical_authorized") {
    overallState = "authorized";
    headline = "Physical power-on authorized";
    nextAction = { label: "Open Package", stage: STAGES.package };
  } else {
    overallState = "review_required";
    headline = "Review package before handoff";
    nextAction = { label: "Open Package", stage: STAGES.package };
  }

  return {
    design: {
      state: designState,
      errors,
      warnings,
      label:
        designState === "not_compiled"
          ? "Not compiled"
          : designState === "drc_errors"
            ? `${errors ?? "?"} DRC error(s)`
            : designState === "drc_clean"
              ? "DRC clean"
              : "DRC unknown",
    },
    copper: {
      state: copperState,
      label: copperLabel,
      detail: copperDetail,
      tier: copperTier,
    },
    bench: {
      state: benchState,
      openGateCount: openGateCount ?? 0,
      criticalOpenCount,
      powerOnAuthorized,
      simulated,
      physical,
      label:
        benchState === "not_started"
          ? "No bench yet"
          : benchState === "gates_open"
            ? `${openGateCount ?? 0} gate(s) open`
            : benchState === "simulated_pass"
              ? "Simulated evidence"
              : benchState === "physical_authorized"
                ? "Power-on authorized"
                : "Bench pending",
    },
    package: {
      state: packageState,
    },
    overall: {
      state: overallState,
      headline,
      nextAction,
    },
  };
}
