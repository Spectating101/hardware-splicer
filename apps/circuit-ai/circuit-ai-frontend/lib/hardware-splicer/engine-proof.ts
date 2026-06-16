import type { BuildGraph } from "@/lib/rules/safety-rules";
import { composeCanvasBuildRemote, preferPythonEngine } from "./client";

export type EngineCompileProof = {
  ok: boolean;
  source: "python";
  kicadDrcPass: boolean;
  kicadDrcErrors: number;
  kicadDrcWarnings: number;
  buildReady: boolean;
  fabricationReady: boolean;
  electricalErrors: number;
  electricalWarnings: number;
  bomReady: boolean;
  gerberReady: boolean;
  blockers: string[];
  verifiedAt: number;
  error?: string;
};

type DesignQualityPayload = {
  kicad_drc_pass?: boolean;
  kicad_drc_errors?: number;
  kicad_drc_warnings?: number;
  drc_pass?: boolean;
  build_ready?: boolean;
  fabrication_ready?: boolean;
  electrical_errors?: number;
  electrical_warnings?: number;
  bom_ready?: boolean;
  gerber_ready?: boolean;
};

type DesignQualityGate = {
  build_ready?: boolean;
  fabrication_ready?: boolean;
  blockers?: string[];
};

function proofFromPayload(
  payload: {
    ok?: boolean;
    design_quality?: DesignQualityPayload;
    design_quality_gate?: DesignQualityGate;
    error?: string;
  },
): EngineCompileProof {
  const quality = payload.design_quality ?? {};
  const gate = payload.design_quality_gate ?? {};
  const kicadErrors = Number(quality.kicad_drc_errors ?? 0);
  const kicadWarnings = Number(quality.kicad_drc_warnings ?? 0);
  const kicadPass =
    quality.kicad_drc_pass === true || (kicadErrors === 0 && quality.drc_pass === true);

  return {
    ok: Boolean(payload.ok),
    source: "python",
    kicadDrcPass: kicadPass,
    kicadDrcErrors: kicadErrors,
    kicadDrcWarnings: kicadWarnings,
    buildReady: Boolean(gate.build_ready ?? quality.build_ready),
    fabricationReady: Boolean(gate.fabrication_ready ?? quality.fabrication_ready),
    electricalErrors: Number(quality.electrical_errors ?? 0),
    electricalWarnings: Number(quality.electrical_warnings ?? 0),
    bomReady: Boolean(quality.bom_ready),
    gerberReady: Boolean(quality.gerber_ready),
    blockers: Array.isArray(gate.blockers) ? gate.blockers.filter(Boolean) : [],
    verifiedAt: Date.now(),
    error: payload.error,
  };
}

export function engineProofUnavailableMessage(): string {
  return (
    "Hardware-Splicer engine is not reachable. Start it with: " +
    "PYTHONPATH=src python3 scripts/hardware_splicer.py serve --port 8090 " +
    "(set HARDWARE_SPLICER_API_URL for the frontend proxy)."
  );
}

export async function verifyCanvasBuildRemote(
  graph: BuildGraph,
  options?: { exportGerber?: boolean },
): Promise<EngineCompileProof> {
  const payload = await composeCanvasBuildRemote(graph, {
    exportGerber: options?.exportGerber ?? false,
  });
  return proofFromPayload(payload);
}

export function shouldRequireEngineForManufacture(): boolean {
  return preferPythonEngine();
}
