export type FileKind =
  | "kicad_pcb"
  | "kicad_sch"
  | "gerber"
  | "bom_csv"
  | "unknown";

export function detectFileKind(filename: string): FileKind {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".kicad_pcb")) return "kicad_pcb";
  if (lower.endsWith(".kicad_sch")) return "kicad_sch";
  if (
    lower.endsWith(".gbr") ||
    lower.endsWith(".gtl") ||
    lower.endsWith(".gbl") ||
    lower.endsWith(".gts") ||
    lower.endsWith(".gbs")
  )
    return "gerber";
  if (lower.endsWith(".csv")) return "bom_csv";
  return "unknown";
}

export function fileKindLabel(kind: FileKind): string {
  const labels: Record<FileKind, string> = {
    kicad_pcb: "KiCad PCB",
    kicad_sch: "KiCad Schematic",
    gerber: "Gerber",
    bom_csv: "BOM CSV",
    unknown: "Unknown",
  };
  return labels[kind];
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function healthLabel(score: number): string {
  if (score >= 80) return "Excellent";
  if (score >= 60) return "Good";
  if (score >= 40) return "Needs Work";
  return "Critical";
}

function scoreFromIssues(
  issues: { severity: string }[]
): number {
  const criticalCount = issues.filter((i) => i.severity === "critical").length;
  const errorCount = issues.filter((i) => i.severity === "error").length;
  const warningCount = issues.filter((i) => i.severity === "warning").length;
  const penalty = criticalCount * 20 + errorCount * 8 + warningCount * 2;
  return Math.max(0, 100 - penalty);
}

export { scoreFromIssues };

export const jarvis = {
  fileDropped(filename: string): string {
    return `I found your file — **${filename}**. Click "Parse board" to extract the circuit structure.`;
  },

  boardFound(filename: string): string {
    return `Board parsed from **${filename}**. I can see the component tree and layer stack. Click "Check issues" to run electrical validation.`;
  },

  validationStart(): string {
    return "Running electrical rules check and DFM analysis…";
  },

  validationClean(): string {
    return "Everything looks clean. No issues found. Your board is ready for the next step.";
  },

  validationIssues(total: number, critical: number): string {
    if (critical > 0) {
      return `Found **${total} issue${total === 1 ? "" : "s"}**, including **${critical} critical**. These need to be fixed before manufacture. Click "See details →" to review them.`;
    }
    return `Found **${total} issue${total === 1 ? "" : "s"}** — no critical blockers. Click "See details →" to review and decide what to fix.`;
  },

  validationError(msg: string): string {
    return `Validation failed: ${msg}. Check that the backend is running and try again.`;
  },

  userPrompt(text: string): string {
    return text;
  },

  defaultResponse(): string {
    return "I'm here. Drop a `.kicad_pcb` file on the canvas or describe what you want to build.";
  },

  proactiveManufacture(hasCritical: boolean): string {
    if (hasCritical) {
      return "Fix the critical issue first, then I can package it for manufacture. Want me to walk you through the fix?";
    }
    return "Board checked. Ready to generate Gerber files, BOM, and assembly guide — takes about 30 seconds.";
  },
};
