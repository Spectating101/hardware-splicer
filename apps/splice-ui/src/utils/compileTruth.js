/** Normalize compile/DRC truth from package gates, API summary, or compose payloads. */

function pick(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return null;
}

export function normalizeCompileTruth({ pkg, quality, compose } = {}) {
  const gates = pkg?.gates || {};
  const dq = quality || compose?.design_quality || {};

  const drcErrors = pick(dq.kicad_drc_errors, dq.drc_errors, gates.kicad_drc_errors);
  const drcWarnings = pick(dq.kicad_drc_warnings, dq.drc_warnings, gates.kicad_drc_warnings);

  const compileOk = pick(
    gates.compile_ok,
    dq.compile_ok,
    dq.drc_pass,
    drcErrors === 0 ? true : drcErrors === null ? null : false,
  );

  return {
    kicad_drc_errors: drcErrors,
    kicad_drc_warnings: drcWarnings,
    copper_tier: pick(dq.copper_tier, gates.copper_tier),
    fab_recommendation: pick(dq.fab_recommendation, gates.fab_recommendation),
    compile_ok: compileOk,
    build_ready: pick(dq.build_ready, gates.build_ready),
    fabrication_ready: pick(dq.fabrication_ready, gates.fabrication_ready),
    electrical_safety_pass: dq.electrical_safety_pass,
    circuit_readiness: dq.circuit_readiness,
    build_id: dq.build_id,
    has_kicad_pcb: dq.has_kicad_pcb,
  };
}

export function compileTruthHeadline(truth) {
  if (!truth) return "Compile status unknown";
  if (truth.compile_ok === false) return "Compile blocked — review errors before bench";
  if (truth.kicad_drc_errors > 0) return `${truth.kicad_drc_errors} KiCad DRC error(s) — not fab-ready`;
  if (truth.fabrication_ready) return "KiCad DRC clean — fabrication checks passed";
  if (truth.build_ready) return "KiCad compile ready — review warnings before fab";
  if (truth.compile_ok) return "KiCad compile passed — preview copper only (not fab-ready)";
  return "Compile status loaded from build artifacts";
}

export function copperTierLabel(tier) {
  if (!tier) return "—";
  const raw = String(tier);
  if (raw.includes("cosmetic") || raw.includes("preview")) return "Preview copper (not fab-ready)";
  return raw.replace(/_/g, " ");
}
