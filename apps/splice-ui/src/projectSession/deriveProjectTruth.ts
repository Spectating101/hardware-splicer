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
 * Physical requires affirmative provenance — simulated===false alone is NOT physical.
 * Copper: copper_tier honesty boundary.
 */

import { sessionHasBuild, sessionHasPackage, STAGES } from "./projectSession.js";

export type StageId = "intake" | "design" | "verify" | "bench" | "package";

export type DesignState =
  | "not_compiled"
  | "unknown"
  | "drc_errors"
  | "drc_clean"
  | "request_mismatch"
  | "electrical_error"
  | "needs_attention";

export type CopperState =
  | "not_available"
  | "preview_only"
  | "review_required"
  | "fab_candidate";

export type BenchState =
  | "not_started"
  | "physical_authorized"
  | "simulated_pass"
  | "gates_open"
  | "authorization_pending";

export type PackageState = "generated" | "missing";

export type OverallState =
  | "needs_design"
  | "needs_verification"
  | "power_on_blocked"
  | "review_required"
  | "authorized";

export type BenchEvidenceKind = "physical" | "simulated";

export interface BenchSessionInput {
  evidence_kind?: BenchEvidenceKind | null;
  physical_capture?: boolean | null;
  capture_provenance?: string | null;
  instrument_capture?: boolean | null;
  validated_physical_capture?: boolean | null;
  open_gate_count?: number | string | null;
  open_gates?: readonly unknown[] | null;
  critical_open_count?: number | string | null;
  power_on_authorized?: boolean | null;
  simulated?: boolean | null;
  source?: string | null;
}

export interface PackageGatesInput {
  evidence_kind?: BenchEvidenceKind | null;
  physical_capture?: boolean | null;
  capture_provenance?: string | null;
  instrument_capture?: boolean | null;
  validated_physical_capture?: boolean | null;
  kicad_drc_errors?: number | string | null;
  kicad_drc_warnings?: number | string | null;
  compile_ok?: boolean | null;
  copper_tier?: string | null;
  open_gate_count?: number | string | null;
  critical_open_count?: number | string | null;
  power_on_authorized?: boolean | null;
  simulated?: boolean | null;
}

export interface DesignQualityInput {
  kicad_drc_errors?: number | string | null;
  drc_errors?: number | string | null;
  kicad_drc_warnings?: number | string | null;
  drc_warnings?: number | string | null;
  copper_tier?: string | null;
}

export interface AgentLoopInput {
  final_kicad_drc_errors?: number | string | null;
  copper_tier?: string | null;
}

export interface RequestFidelityMissingPart {
  module_id?: string;
  names?: readonly string[] | null;
  requested?: number;
  in_design?: number;
  unknown_module_id?: boolean;
  did_you_mean?: readonly string[] | null;
}

export interface ElectricalRepairInput {
  summary?: string;
  requires_person?: boolean;
  physical_steps?: readonly string[] | null;
}

export interface ElectricalIssueInput {
  level?: string;
  message?: string;
  requires_person?: boolean;
  repairs?: readonly ElectricalRepairInput[] | null;
}

export interface ProjectProblemRepair {
  summary: string | undefined;
  requiresPerson: boolean;
  steps: readonly string[];
}

export interface ProjectProblem {
  message: string;
  repairs: ProjectProblemRepair[];
  // True when only a person can clear it and HS has no repair step to show for it.
  needsPerson?: boolean;
}

export interface RequestFidelityInput {
  status?: string | null;
  missing_parts?: readonly RequestFidelityMissingPart[] | null;
}

export interface ProjectPackageInput {
  gates?: PackageGatesInput | null;
  build_dir?: string | null;
}

export interface ProjectTruthSessionInput {
  intakeComplete?: boolean;
  buildDir?: string | null;
  projectPackage?: ProjectPackageInput | null;
  designQuality?: DesignQualityInput | null;
  agentLoop?: AgentLoopInput | null;
  benchSession?: BenchSessionInput | null;
  displayResult?: {
    design_quality?: DesignQualityInput | null;
    bench_session?: BenchSessionInput | null;
    design_quality_gate?: {
      build_ready?: boolean | null;
      blockers?: readonly string[] | null;
      request_fidelity?: RequestFidelityInput | null;
      summary?: {
        electrical_issues?: readonly ElectricalIssueInput[] | null;
      } | null;
    } | null;
  } | null;
  composeResult?: {
    agent_loop?: AgentLoopInput | null;
  } | null;
}

export interface ProjectNextAction {
  label: string;
  stage: StageId;
}

export interface ProjectTruth {
  design: {
    state: DesignState;
    errors: number | null;
    warnings: number | null;
    detail: string;
    problems: ProjectProblem[];
    label: string;
  };
  copper: {
    state: CopperState;
    label: string;
    detail: string;
    tier: string | null;
  };
  bench: {
    state: BenchState;
    openGateCount: number;
    criticalOpenCount: number;
    powerOnAuthorized: boolean;
    simulated: boolean;
    physical: boolean;
    label: string;
  };
  package: {
    state: PackageState;
  };
  overall: {
    state: OverallState;
    headline: string;
    nextAction: ProjectNextAction;
  };
}

function pick<T>(...values: ReadonlyArray<T | null | undefined | "">): T | null {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return null;
}

function numOrNull(value: unknown): number | null {
  if (value === undefined || value === null || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/** Affirmative physical provenance only — never infer from simulated===false. */
export function hasAffirmativePhysicalEvidence(
  bench: BenchSessionInput | null | undefined,
  gates: PackageGatesInput | null | undefined = {},
): boolean {
  if (!bench && !gates) return false;
  const kind = pick(bench?.evidence_kind, gates?.evidence_kind);
  if (kind === "physical") return true;
  if (bench?.physical_capture === true || gates?.physical_capture === true) return true;
  if (bench?.capture_provenance === "physical" || gates?.capture_provenance === "physical") {
    return true;
  }
  if (bench?.instrument_capture === true || gates?.instrument_capture === true) return true;
  if (
    (bench?.validated_physical_capture === true || gates?.validated_physical_capture === true) &&
    kind !== "simulated"
  ) {
    return true;
  }
  return false;
}

function designLabel(designState: DesignState, errors: number | null): string {
  switch (designState) {
    case "not_compiled":
      return "Not compiled";
    case "electrical_error":
      return "Electrical problem";
    case "needs_attention":
      return "Not build-ready";
    case "request_mismatch":
      return "Missing requested part";
    case "drc_errors":
      return `${errors ?? "?"} DRC error(s)`;
    case "drc_clean":
      return "DRC clean";
    default:
      return "DRC unknown";
  }
}

export function deriveProjectTruth(session: ProjectTruthSessionInput = {}): ProjectTruth {
  const pkg = session.projectPackage || {};
  const gates = pkg.gates || {};
  const dq = session.designQuality || session.displayResult?.design_quality || {};
  const agent = session.agentLoop || session.composeResult?.agent_loop || {};
  const bench = session.benchSession || session.displayResult?.bench_session || null;

  const errors = numOrNull(
    pick(dq.kicad_drc_errors, dq.drc_errors, agent.final_kicad_drc_errors, gates.kicad_drc_errors),
  );
  const warnings = numOrNull(pick(dq.kicad_drc_warnings, dq.drc_warnings, gates.kicad_drc_warnings));

  let designState: DesignState = "not_compiled";
  if (!sessionHasBuild(session)) {
    designState = "not_compiled";
  } else if (errors == null && gates.compile_ok !== true && gates.compile_ok !== false) {
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

  const gate = session.displayResult?.design_quality_gate;
  const fidelity = gate?.request_fidelity;
  const requestMismatch = sessionHasBuild(session) && fidelity?.status === "mismatch";
  if (requestMismatch) designState = "request_mismatch";
  // A design the electrical check rejects is not a DRC failure; say what it found, in its own words.
  const electricalErrors = sessionHasBuild(session)
    ? (gate?.summary?.electrical_issues || []).filter(
        (issue): issue is ElectricalIssueInput & { message: string } => issue?.level === "error" && Boolean(issue?.message),
      )
    : [];
  const electricalError = !requestMismatch && electricalErrors.length > 0;
  if (electricalError) designState = "electrical_error";
  // Electrical errors are listed even when a missing requested part is the state said first.
  const electricalDetail = electricalErrors.map((issue) => issue.message).join(" ");
  // A clean DRC is not a build-ready design. When the quality gate says it is not (a strap only a
  // person can set, a failing KiCad ERC, a goal the design does not cover), say so and list why.
  const gateBlocked = sessionHasBuild(session) && gate?.build_ready === false;
  const needsAttention = gateBlocked && designState === "drc_clean";
  if (needsAttention) designState = "needs_attention";
  const issuesByMessage = new Map<string, ElectricalIssueInput>(
    (gate?.summary?.electrical_issues || []).filter((i) => i?.message).map((i) => [String(i.message), i]),
  );
  const gateProblems: ProjectProblem[] = [];
  if (needsAttention) {
    const messages = [
      ...(gate?.blockers || []).map(String),
      ...[...issuesByMessage.values()].filter((i) => i.requires_person).map((i) => String(i.message)),
    ];
    for (const message of [...new Set(messages)]) {
      const issue = issuesByMessage.get(message);
      const repairs = (issue?.repairs || []).map((repair) => ({
        summary: repair.summary,
        requiresPerson: Boolean(repair.requires_person),
        steps: repair.physical_steps || [],
      }));
      gateProblems.push({ message, repairs, needsPerson: Boolean(issue?.requires_person) });
    }
  }
  const gateDetail = gateProblems.map((p) => p.message).join(" ");
  // Each problem as data, so a panel can show it in plain view and say who can fix it.
  const problems = [
    ...(requestMismatch
      ? (fidelity?.missing_parts || []).map((row) => ({
          message: `Design leaves out requested part ${row.module_id}: requested ${row.requested}, design has ${row.in_design} (${(row.names || []).join(", ")}).${
            row.unknown_module_id
              ? ` ${row.module_id} is not a part id HS knows.${row.did_you_mean?.length ? ` Did you mean ${row.did_you_mean.join(" or ")}?` : " Look the part up in the module catalog."}`
              : ""
          }`,
          repairs: [],
        }))
      : []),
    ...gateProblems,
    ...(electricalErrors.length > 0
      ? electricalErrors.map((issue) => ({
          message: issue.message,
          repairs: (issue.repairs || []).map((repair) => ({
            summary: repair.summary,
            requiresPerson: Boolean(repair.requires_person),
            steps: repair.physical_steps || [],
          })),
        }))
      : []),
  ];
  const requestDetail = requestMismatch
    ? (fidelity!.missing_parts || [])
        .map(
          (row) =>
            `Design leaves out requested part ${row.module_id}: requested ${row.requested}, design has ${row.in_design} (${(row.names || []).join(", ")}).`,
        )
        .join(" ")
    : "";

  const copperTier = pick(dq.copper_tier, gates.copper_tier, agent.copper_tier);
  let copperState: CopperState = "not_available";
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
      gates.evidence_kind === "simulated" ||
      String(bench?.source || "").includes("simulat"),
  );
  const physical = hasAffirmativePhysicalEvidence(bench, gates);

  let benchState: BenchState = "not_started";
  if (!bench && openGateCount == null && !sessionHasBuild(session)) {
    benchState = "not_started";
  } else if (powerOnAuthorized && physical && !simulated) {
    benchState = "physical_authorized";
  } else if (powerOnAuthorized && simulated) {
    benchState = "simulated_pass";
  } else if ((openGateCount ?? 0) > 0 || criticalOpenCount > 0) {
    benchState = "gates_open";
  } else if (bench || gates.open_gate_count != null) {
    // Zero open gates without simulated/physical authorization evidence
    if (simulated && !powerOnAuthorized) {
      benchState = "authorization_pending";
    } else if (simulated) {
      benchState = "simulated_pass";
    } else {
      benchState = "authorization_pending";
    }
  }

  const packageState: PackageState = sessionHasPackage(session) ? "generated" : "missing";

  let overallState: OverallState = "needs_design";
  let headline = "Complete Intake, then design the board";
  let nextAction: ProjectNextAction = { label: "Continue Intake", stage: STAGES.intake };

  if (!session.intakeComplete) {
    overallState = "needs_design";
    headline = "Finish Intake to unlock Design";
    nextAction = { label: "Continue Intake", stage: STAGES.intake };
  } else if (!sessionHasBuild(session)) {
    overallState = "needs_design";
    headline = "Design and compile the board";
    nextAction = { label: "Open Design", stage: STAGES.design };
  } else if (designState === "electrical_error") {
    overallState = "needs_verification";
    headline = "The design has an electrical problem";
    nextAction = { label: "Open Verify", stage: STAGES.verify };
  } else if (designState === "needs_attention") {
    overallState = "needs_verification";
    headline = gateProblems.some((p) => p.needsPerson || p.repairs.some((r) => r.requiresPerson))
      ? "The design needs you before it is build-ready"
      : "The design is not build-ready";
    nextAction = { label: "Open Verify", stage: STAGES.verify };
  } else if (designState === "request_mismatch") {
    overallState = "needs_verification";
    headline = "The design leaves out a part you asked for";
    nextAction = { label: "Open Verify", stage: STAGES.verify };
  } else if (designState === "drc_errors" || designState === "unknown") {
    overallState = "needs_verification";
    headline = "Review design verification before handoff";
    nextAction = { label: "Open Verify", stage: STAGES.verify };
  } else if (benchState === "gates_open" || benchState === "not_started") {
    overallState = "power_on_blocked";
    headline = "Close bench gates before power-on";
    nextAction = { label: "Review Bench", stage: STAGES.bench };
  } else if (benchState === "authorization_pending") {
    overallState = "power_on_blocked";
    headline = "Bench evidence needs review before power-on";
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
      detail: [requestDetail, electricalDetail].filter(Boolean).join(" ") || gateDetail,
      problems,
      label: designLabel(designState, errors),
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
            : benchState === "authorization_pending"
              ? "Measurements recorded · authorization pending"
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
