import { normalizeCompileTruth, compileTruthHeadline } from "../utils/compileTruth.js";

export function extractStudioDrc(composeResult) {
  const quality = composeResult?.design_quality || {};
  const truth = normalizeCompileTruth({ compose: composeResult, quality });
  const loop = quality.drc_fix_loop || null;
  const attempts = loop?.attempts || [];
  const lastAttempt = attempts.length ? attempts[attempts.length - 1] : null;
  const fixup = lastAttempt?.drc_fixup || composeResult?.graph?.drc_fixup || null;
  const violations = (quality.violations || [])
    .concat(
      (composeResult?.violations || []).map((row) => ({
        severity: row.severity || "error",
        type: row.type,
        description: row.description || row.message,
      })),
    )
    .filter((row) => String(row.severity || "").toLowerCase() === "error");

  return {
    truth,
    headline: compileTruthHeadline(truth),
    loop,
    attempts,
    agentLoop: composeResult?.agent_loop || null,
    agentRounds: composeResult?.agent_loop?.rounds || [],
    resolved: Boolean(loop?.resolved || composeResult?.agent_loop?.resolved),
    fixup,
    violations,
    outDir: composeResult?.out_dir || null,
    ok: Boolean(composeResult?.ok),
    mode: composeResult?.mode || null,
    composeMode: composeResult?.compose_mode || null,
    moduleIds: composeResult?.module_ids || [],
    hasPackage: Boolean(composeResult?.project_package),
    copperTier: composeResult?.agent_loop?.copper_tier || quality.copper_tier || null,
    fabRecommendation:
      composeResult?.agent_loop?.fab_recommendation || quality.fab_recommendation || null,
  };
}

export function bumpDrcFixup(current = {}) {
  const base = { ...current };
  base.edge_pad_extra_mm = Number(base.edge_pad_extra_mm || 0) + 0.35;
  base.module_gap_extra_mm = Number(base.module_gap_extra_mm || 0) + 4;
  base.via_clearance_mm = Math.max(Number(base.via_clearance_mm || 0.21), 0.21) + 0.06;
  return base;
}

export function agentStepLabel(step) {
  switch (step) {
    case "compose":
      return "Compose graph";
    case "compile":
      return "KiCad compile";
    case "drc":
      return "DRC check";
    case "fix":
      return "Geometry fixup";
    case "done":
      return "Complete";
    default:
      return step;
  }
}
