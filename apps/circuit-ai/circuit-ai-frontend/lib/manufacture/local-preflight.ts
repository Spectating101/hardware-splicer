import type { BuildGraph } from "@/lib/rules/safety-rules";
import { analyzeBuild } from "@/lib/rules/safety-rules";
import { buildGraphToGeometry } from "@/lib/pcb/build-to-geometry";
import { runDrc } from "@/lib/pcb/drc";
import { serializeBuildToKicadPcb } from "@/lib/kicad-serializer";

export interface LocalPreflightResult {
  manufacturing_ready: boolean;
  critical: number;
  errors: number;
  warnings: number;
  issues: Array<{ severity: string; issue: string; solution?: string }>;
  kicad_valid: boolean;
  source: "local";
}

/** Offline DFM-style check using the same rules as /build — no backend required. */
export function runLocalManufacturePreflight(graph: BuildGraph): LocalPreflightResult {
  const issues: LocalPreflightResult["issues"] = [];

  const safety = analyzeBuild(graph);
  for (const w of safety) {
    if (w.level === "error") {
      issues.push({
        severity: "error",
        issue: w.message,
        solution: "Fix wiring or part choice on the breadboard before ordering boards.",
      });
    } else if (w.level === "warn") {
      issues.push({
        severity: "warning",
        issue: w.message,
        solution: "Review before powering on or sending to fab.",
      });
    }
  }

  const drc = runDrc(buildGraphToGeometry(graph));
  for (const v of drc.violations) {
    if (v.severity === "error") {
      issues.push({
        severity: "error",
        issue: v.message,
        solution: "Adjust module placement or routing on the canvas.",
      });
    } else if (v.severity === "warn") {
      issues.push({
        severity: "warning",
        issue: v.message,
      });
    }
  }

  if (graph.nodes.length === 0) {
    issues.push({
      severity: "error",
      issue: "Board is empty — add parts before manufacturing.",
    });
  }

  if (graph.wires.length < 2) {
    issues.push({
      severity: "warning",
      issue: "Very few connections — double-check wiring before fab.",
    });
  }

  let kicad_valid = false;
  try {
    const pcb = serializeBuildToKicadPcb(graph);
    kicad_valid = pcb.includes("(kicad_pcb") && pcb.includes("(footprint");
    if (!kicad_valid) {
      issues.push({
        severity: "error",
        issue: "Could not build a valid KiCad board file from this design.",
        solution: "Try rebuilding wiring or loading a catalog recipe.",
      });
    }
  } catch {
    issues.push({
      severity: "error",
      issue: "KiCad export failed for this layout.",
    });
  }

  const errors = issues.filter((i) => i.severity === "error").length;
  const critical = issues.filter((i) => i.severity === "critical").length;
  const warnings = issues.filter((i) => i.severity === "warning").length;

  return {
    manufacturing_ready: errors === 0 && critical === 0 && kicad_valid && graph.nodes.length > 0,
    critical,
    errors,
    warnings,
    issues,
    kicad_valid,
    source: "local",
  };
}
