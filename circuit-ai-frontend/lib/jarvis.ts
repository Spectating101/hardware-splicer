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

function scoreFromIssues(issues: { severity: string }[]): number {
  const criticalCount = issues.filter((i) => i.severity === "critical").length;
  const errorCount = issues.filter((i) => i.severity === "error").length;
  const warningCount = issues.filter((i) => i.severity === "warning").length;
  const penalty = criticalCount * 20 + errorCount * 8 + warningCount * 2;
  return Math.max(0, 100 - penalty);
}

export { scoreFromIssues };

// ─── Intent parsing ──────────────────────────────────────────────────────────

export type JarvisIntent =
  | { type: "validate" }
  | { type: "manufacture" }
  | { type: "show_issues" }
  | { type: "status" }
  | { type: "acknowledge" }
  | { type: "undo" }
  | { type: "clear" }
  | { type: "help" }
  | { type: "unknown"; text: string };

export function parseIntent(text: string): JarvisIntent {
  const t = text.toLowerCase().trim();
  if (/\b(validate|check\s+issue|run\s+erc|erc|drc|check\s+board)\b/.test(t))
    return { type: "validate" };
  if (
    /\b(manufactur|gerber|package\s+for|generate\s+package|send\s+to\s+fab|produce|fabricat|build\s+it)\b/.test(
      t
    )
  )
    return { type: "manufacture" };
  if (
    /(\b(show|open|see|view)\b.*\b(issue|error|problem|wrong|warning)\b)|(\bwhat.?s wrong\b)|\bissues?\b/.test(
      t
    )
  )
    return { type: "show_issues" };
  if (/\b(status|progress|where\s+are\s+we|what.?s\s+(the\s+)?status|summary)\b/.test(t))
    return { type: "status" };
  if (
    /\b(acknowledge|ack|dismiss|ignore|suppress|accept)\b.*\b(warning|issue|error)\b/.test(t) ||
    /\b(mark|set)\b.*\b(warning|issue).*\b(ok|okay|done|resolved|fixed)\b/.test(t)
  )
    return { type: "acknowledge" };
  if (/\bundo\b/.test(t)) return { type: "undo" };
  if (/\b(clear|reset|new\s+project|start\s+over|fresh)\b/.test(t))
    return { type: "clear" };
  if (/\b(help|commands?|what\s+can\s+you|how\s+do)\b/.test(t))
    return { type: "help" };
  return { type: "unknown", text };
}

export interface JarvisContext {
  hasBoardNode: boolean;
  hasValidation: boolean;
  hasManufacturing: boolean;
  hasCriticals: boolean;
  activeIssueCount: number;
  boardName?: string;
  healthScore?: number;
  componentCount?: number;
  layerCount?: number;
}

export function contextualResponse(intent: JarvisIntent, ctx: JarvisContext): string {
  switch (intent.type) {
    case "validate":
      if (!ctx.hasBoardNode)
        return "Drop a `.kicad_pcb` file on the canvas first, then I'll run the electrical rules check.";
      if (ctx.hasValidation)
        return `Already validated **${ctx.boardName ?? "this board"}** — health score is **${ctx.healthScore}/100**. Drop a new file or say **clear** to start fresh.`;
      return `Running ERC on **${ctx.boardName ?? "the board"}**…`;

    case "manufacture":
      if (!ctx.hasBoardNode)
        return "I need a board first. Drop a `.kicad_pcb` file on the canvas.";
      if (!ctx.hasValidation)
        return `Run validation first — I need to confirm there are no critical issues in **${ctx.boardName ?? "the board"}** before generating the package.`;
      if (ctx.hasCriticals)
        return `There are **${ctx.activeIssueCount} unresolved critical issues** in **${ctx.boardName ?? "the board"}**. Resolve or acknowledge them first.`;
      if (ctx.hasManufacturing)
        return `Manufacturing package for **${ctx.boardName ?? "the board"}** was already generated. Open the board drawer → Manufacture tab to see the files.`;
      return `Generating manufacturing package for **${ctx.boardName ?? "the board"}**…`;

    case "show_issues":
      if (!ctx.hasValidation)
        return "No validation results yet. Say **validate** and I'll run the ERC check.";
      if (ctx.activeIssueCount === 0)
        return `**${ctx.boardName ?? "The board"}** is clean — no active issues. It's ready to manufacture.`;
      return `Opening the issues panel — ${ctx.activeIssueCount} active issue${ctx.activeIssueCount === 1 ? "" : "s"} found.`;

    case "status": {
      if (!ctx.hasBoardNode)
        return "Nothing on the canvas yet. Drop a `.kicad_pcb` file to get started.";
      const parts: string[] = [];
      parts.push(
        `**${ctx.boardName ?? "Board"}**${ctx.componentCount ? ` — ${ctx.componentCount} components` : ""}${ctx.layerCount ? `, ${ctx.layerCount} layers` : ""}`
      );
      if (!ctx.hasValidation) {
        parts.push("ERC not run yet. Say **validate** to check for issues.");
      } else if (ctx.activeIssueCount === 0) {
        parts.push(`Validation: **${ctx.healthScore}/100** — no active issues.`);
      } else {
        parts.push(
          `Validation: **${ctx.healthScore}/100** — ${ctx.activeIssueCount} active issue${ctx.activeIssueCount === 1 ? "" : "s"}${ctx.hasCriticals ? " (critical)" : ""}.`
        );
      }
      if (ctx.hasManufacturing) {
        parts.push("Manufacturing package: **ready**.");
      } else if (ctx.hasValidation && !ctx.hasCriticals) {
        parts.push("Ready to manufacture — say **manufacture** to generate files.");
      }
      return parts.join("  \n");
    }

    case "acknowledge":
      if (!ctx.hasValidation)
        return "No validation results to acknowledge. Run **validate** first.";
      if (ctx.activeIssueCount === 0)
        return "All issues are already acknowledged.";
      return `Acknowledging all warnings in **${ctx.boardName ?? "the board"}**…`;

    case "undo":
      return "Undone.";

    case "clear":
      return "Workspace cleared. Drop a file or describe what you want to build.";

    case "help":
      return [
        "Here's what I understand:",
        "**validate** — run ERC and DFM check on the board",
        "**manufacture** — generate Gerbers, BOM, and assembly guide",
        "**show issues** — open the validation panel",
        "**status** — project summary",
        "**acknowledge warnings** — dismiss all non-critical issues",
        "**undo** — undo the last action (or Ctrl+Z)",
        "**clear** — reset the workspace",
        "Or drop a `.kicad_pcb` file directly onto the canvas.",
      ].join("  \n");

    default: {
      const { text } = intent as { type: "unknown"; text: string };
      if (!ctx.hasBoardNode)
        return text
          ? `I heard you — but I need a board to work with first. Drop a \`.kicad_pcb\` file.`
          : "Drop a `.kicad_pcb` file on the canvas or describe what you want to build.";
      if (!ctx.hasValidation)
        return `I can see **${ctx.boardName}** on the canvas. Say **validate** to run the electrical rules check, or **help** to see what I can do.`;
      if (ctx.hasCriticals)
        return `**${ctx.boardName}** has **${ctx.activeIssueCount} critical issue${ctx.activeIssueCount === 1 ? "" : "s"}** that need attention before manufacturing. Say **show issues** to review them.`;
      if (!ctx.hasManufacturing)
        return `**${ctx.boardName}** is validated — health score **${ctx.healthScore}/100**. Say **manufacture** to generate the Gerbers and BOM.`;
      return `**${ctx.boardName}** is fully processed — validated and packaged. The manufacturing files are ready in the rightmost node.`;
    }
  }
}

// ─── JARVIS narration library ─────────────────────────────────────────────────

export const jarvis = {
  fileDropped(filename: string): string {
    return `I found **${filename}**. Click "Parse board" to extract the circuit structure.`;
  },

  duplicateFile(filename: string): string {
    return `**${filename}** is already on the canvas. Remove the existing node first if you want to replace it.`;
  },

  boardFound(filename: string, componentCount?: number, layerCount?: number): string {
    const detail =
      componentCount && layerCount
        ? ` — **${componentCount} components** across **${layerCount} layers**`
        : "";
    const characterize = (() => {
      if (!componentCount || !layerCount) return "";
      if (componentCount < 10 && layerCount <= 2) return " Looks like a minimal proof-of-concept.";
      if (componentCount < 30 && layerCount <= 2) return " Looks like a simple 2-layer prototype.";
      if (componentCount < 60 && layerCount <= 4) return " Medium-complexity board.";
      if (componentCount < 150) return " High-component-count design — take care with clearances.";
      return " Dense, high-layer board — expect DFM scrutiny.";
    })();
    return `Board parsed from **${filename}**${detail}.${characterize} Say **validate** or click "Check issues" to run the electrical rules check.`;
  },

  validationStart(): string {
    return "Running electrical rules check and DFM analysis…";
  },

  validationClean(): string {
    return "All clean. No issues found. The board is ready to manufacture — say **manufacture** or click the button.";
  },

  validationIssues(total: number, critical: number): string {
    if (critical > 0) {
      return `Found **${total} issue${total === 1 ? "" : "s"}**, including **${critical} critical**. These must be resolved before manufacture. Click "See details →" to review.`;
    }
    return `Found **${total} issue${total === 1 ? "" : "s"}** — no critical blockers. Review and decide what to fix, then say **manufacture** when ready.`;
  },

  validationError(msg: string): string {
    return `Validation failed: ${msg}. Check that the Circuit-AI backend is running and try again.`;
  },

  proactiveManufacture(hasCritical: boolean): string {
    if (hasCritical) {
      return "Fix the critical issues first, then I can package it for manufacture.";
    }
    return "Board looks good. Say **manufacture** or click the button to generate Gerbers, BOM, and assembly guide.";
  },

  manufactureStart(boardName: string): string {
    return `Generating manufacturing package for **${boardName}** — Gerbers, drill files, BOM, and assembly guide.`;
  },

  manufactureDone(gerberCount: number, boardName: string): string {
    return `Manufacturing package for **${boardName}** is ready. **${gerberCount} Gerber files**, BOM, and assembly guide generated.`;
  },

  manufactureError(msg: string): string {
    return `Manufacturing failed: ${msg}. Check that the Mecha-Splicer backend is running.`;
  },

  defaultResponse(): string {
    return "I'm here. Drop a `.kicad_pcb` file on the canvas or describe what you want to build.";
  },
};
