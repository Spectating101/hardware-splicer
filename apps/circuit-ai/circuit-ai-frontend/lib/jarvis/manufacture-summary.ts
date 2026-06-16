/** Plain-language manufacture / DFM feedback for Jarvis. */

import type { LocalPreflightResult } from "@/lib/manufacture/local-preflight";
import type { EngineCompileProof } from "@/lib/hardware-splicer/engine-proof";

export interface ManufactureJarvisResult {
  ok: boolean;
  detail: string;
  manufacturingReady?: boolean;
  blockers?: string[];
  source?: "backend" | "local" | "engine";
}

interface DfmIssue {
  severity?: string;
  issue?: string;
  solution?: string;
}

function blockersFromIssues(issues: DfmIssue[], limit = 3): string[] {
  return issues
    .filter((it) => it.severity === "critical" || it.severity === "error")
    .slice(0, limit)
    .map((it) => {
      const fix = it.solution ? ` (${it.solution})` : "";
      return `${it.issue ?? "layout issue"}${fix}`;
    });
}

export function formatLocalManufactureSummary(local: LocalPreflightResult): ManufactureJarvisResult {
  const blockers = blockersFromIssues(local.issues);

  if (local.manufacturing_ready) {
    return {
      ok: true,
      manufacturingReady: true,
      source: "local",
      blockers: [],
      detail: "Local layout check passed — wiring looks safe and the board file exports cleanly. Download the KiCad file or use a fab's online uploader. (Backend fab service wasn't reachable; this used the on-device checker.)",
    };
  }

  const blockerText = blockers.length > 0
    ? blockers.join("; ")
    : `${local.errors} issue(s) block manufacturing.`;

  return {
    ok: false,
    manufacturingReady: false,
    source: "local",
    blockers,
    detail: `Local check found problems before ordering — ${blockerText} Fix them on the canvas, then ask again.`,
  };
}

export function formatEngineManufactureSummary(proof: EngineCompileProof): ManufactureJarvisResult {
  const blockers = [
    ...proof.blockers,
    ...(proof.kicadDrcPass ? [] : [`KiCad DRC reported ${proof.kicadDrcErrors} error(s).`]),
    ...(proof.electricalErrors > 0 ? [`${proof.electricalErrors} electrical safety error(s).`] : []),
    ...(proof.bomReady ? [] : ["BOM is not ready on the engine compile."]),
    ...(proof.gerberReady ? [] : ["Gerber export was not produced — re-run Manufacture with the engine online."]),
  ].filter(Boolean);

  const ready = proof.fabricationReady && proof.kicadDrcPass && proof.electricalErrors === 0;

  if (ready) {
    return {
      ok: true,
      manufacturingReady: true,
      source: "engine",
      blockers: [],
      detail:
        "KiCad compile + DRC passed on the Python engine. Gerbers and BOM were generated — this is the authoritative fab check, not the canvas preview.",
    };
  }

  const blockerText = blockers.length > 0
    ? blockers.slice(0, 3).join("; ")
    : "Engine compile did not reach fabrication-ready.";

  return {
    ok: false,
    manufacturingReady: false,
    source: "engine",
    blockers: blockers.slice(0, 5),
    detail: `Engine blocked manufacturing — ${blockerText} Fix wiring or module choice, then tap Manufacture again.`,
  };
}

export function formatManufactureJarvisSummary(input: {
  dfm?: {
    manufacturing_ready: boolean;
    critical: number;
    errors: number;
    warnings: number;
    issues?: DfmIssue[];
  };
  gerber?: { manufacturing_ready?: boolean; filename?: string };
  error?: string;
  local?: LocalPreflightResult;
  engine?: EngineCompileProof;
}): ManufactureJarvisResult {
  if (input.engine) {
    return formatEngineManufactureSummary(input.engine);
  }

  if (input.local) {
    return formatLocalManufactureSummary(input.local);
  }

  if (input.error && input.dfm) {
    // partial backend — still format dfm if we have it
  } else if (input.error) {
    return {
      ok: false,
      detail: `Board-ordering service unreachable (${input.error}). Say "order boards made" again — I'll run a local layout check instead.`,
    };
  }

  const dfm = input.dfm;
  if (!dfm) {
    return {
      ok: false,
      detail: "Manufacturing check didn't return results. I'll use the local checker on your next try.",
    };
  }

  const blockers = blockersFromIssues(dfm.issues ?? []);

  if (dfm.manufacturing_ready) {
    const gerberNote = input.gerber?.filename
      ? ` Gerber files are ready (${input.gerber.filename}).`
      : "";
    return {
      ok: true,
      manufacturingReady: true,
      source: "backend",
      detail: `Good news — this board looks ready to send to a fab.${gerberNote} Check the Manufacture panel for download links and cost estimates.`,
      blockers: [],
    };
  }

  const count = dfm.critical + dfm.errors;
  const blockerText = blockers.length > 0
    ? blockers.join("; ")
    : `${count} layout issue(s) need fixing before ordering.`;

  return {
    ok: false,
    manufacturingReady: false,
    source: "backend",
    blockers,
    detail: `Not quite ready to order yet — ${blockerText} Say "show me the circuit board" to review, or fix the layout and ask again.`,
  };
}
