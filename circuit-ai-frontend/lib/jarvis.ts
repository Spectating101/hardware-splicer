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

// ─── Board insights ──────────────────────────────────────────────────────────

export interface BoardInsight {
  label: string;
  body: string;
  level: "info" | "tip" | "warn";
}

export function generateBoardInsights(
  componentCount: number,
  layerCount: number,
  netCount?: number,
  healthScore?: number
): BoardInsight[] {
  const insights: BoardInsight[] = [];

  // Layer count observations
  if (layerCount === 1) {
    insights.push({ level: "warn", label: "Single-layer board", body: "1-layer designs limit routing options and EMI shielding. Consider 2-layer if trace density is tight." });
  } else if (layerCount === 2) {
    insights.push({ level: "info", label: "2-layer PCB", body: "Standard 2-layer design — cost-effective for most projects. Keep ground plane on B.Cu for best EMI performance." });
  } else if (layerCount >= 6) {
    insights.push({ level: "tip", label: `${layerCount}-layer stack-up`, body: "High layer count suggests controlled impedance or dense routing requirements. Confirm your fab's stack-up matches your design intent." });
  } else if (layerCount % 2 !== 0) {
    insights.push({ level: "warn", label: `${layerCount}-layer (odd)`, body: "Odd layer counts can cause warping during reflow. Most fabs recommend even layer counts." });
  }

  // Component density
  const density = componentCount / Math.max(1, layerCount);
  if (componentCount > 150) {
    insights.push({ level: "warn", label: "High component density", body: `${componentCount} components — expect DFM scrutiny. Verify minimum clearances on BGA and fine-pitch parts.` });
  } else if (componentCount < 10 && layerCount <= 2) {
    insights.push({ level: "info", label: "Minimal design", body: `${componentCount} components — small footprint. Good candidate for panelization to reduce per-unit fab cost.` });
  } else if (density > 40) {
    insights.push({ level: "tip", label: "Dense per-layer", body: `${Math.round(density)} components/layer average. Tight routing — run DRC before ordering.` });
  }

  // Net count observations
  if (netCount && netCount > 0) {
    const netRatio = netCount / componentCount;
    if (netRatio > 3) {
      insights.push({ level: "tip", label: "High net-to-component ratio", body: `${netCount} nets across ${componentCount} components. Complex signal routing — verify no unconnected nets in schematic.` });
    }
  }

  // Health score tips
  if (healthScore !== undefined && healthScore < 60) {
    insights.push({ level: "warn", label: "Low health score", body: `Score of ${healthScore}/100 indicates multiple rule violations. Resolve critical issues before ordering — fab rejection is likely otherwise.` });
  } else if (healthScore !== undefined && healthScore >= 90) {
    insights.push({ level: "tip", label: "Clean design", body: `Score ${healthScore}/100 — excellent. This board is in good shape for production.` });
  }

  return insights.slice(0, 3); // cap at 3 insights
}

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
  | { type: "next" }
  | { type: "open_board" }
  | { type: "open_mfg" }
  | { type: "unknown"; text: string };

export function parseIntent(text: string): JarvisIntent {
  const t = text.toLowerCase().trim();
  if (/\b(validate|check\s+issue|run\s+erc|erc|drc|check\s+board|re-?validate|run\s+check)\b/.test(t))
    return { type: "validate" };
  if (
    /\b(manufactur|gerber|package\s+for|generate\s+package|send\s+to\s+fab|produce|fabricat|build\s+it|ready\s+to\s+ship|order\s+(the\s+)?board|zip.*(file|gerber)|submit.*(fab|board))\b/.test(t)
  )
    return { type: "manufacture" };
  if (
    /(\b(show|open|see|view|list)\b.*\b(issue|error|problem|wrong|warning|fix)\b)|(\bwhat.?s wrong\b)|\bissues?\b|(\bshow\s+me\b)/.test(t) ||
    /\b(bugs?|defect|violation|drc\s+error)\b/.test(t)
  )
    return { type: "show_issues" };
  if (/\b(status|progress|where\s+are\s+we|what.?s\s+(the\s+)?status|summary|how.?s\s+(the\s+)?(board|project|design)|health\b|score\b|overview)\b/.test(t))
    return { type: "status" };
  if (
    /\b(acknowledge|ack|dismiss|ignore|suppress|accept|skip)\b.*\b(warning|issue|error)\b/.test(t) ||
    /\b(mark|set)\b.*\b(warning|issue).*\b(ok|okay|done|resolved|fixed)\b/.test(t) ||
    /\b(that.?s\s+fine|good\s+enough|acceptable|live\s+with)\b/.test(t)
  )
    return { type: "acknowledge" };
  if (/\bundo\b/.test(t)) return { type: "undo" };
  if (/\b(clear|reset|new\s+project|start\s+(over|fresh|again)|wipe)\b/.test(t))
    return { type: "clear" };
  if (/\b(help|commands?|what\s+can\s+you|how\s+do\s+i|what\s+do\s+you)\b/.test(t))
    return { type: "help" };
  if (/\b(next|what\s+(should|do)\s+i|what.?s\s+next|what\s+now|proceed|continue|done|looks?\s+good|looks?\s+(ok|okay|fine)|good\s+to\s+go|all\s+good)\b/.test(t))
    return { type: "next" };
  if (/\b(open|inspect|view|show)\b.*\b(board|pcb|schematic|design|layout)\b|\bboard\s+(detail|info|drawer)\b/.test(t))
    return { type: "open_board" };
  if (/\b(open|view|show|download|get|grab)\b.*\b(mfg|manufactur|package|gerber|files?|output|zip)\b|\bpackage\s+detail\b/.test(t))
    return { type: "open_mfg" };
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
  topIssue?: { what: string; fix: string; severity: string };
}

export function contextualResponse(intent: JarvisIntent, ctx: JarvisContext): string {
  switch (intent.type) {
    case "validate":
      if (!ctx.hasBoardNode)
        return "Drop a `.kicad_pcb` file on the canvas first, then I'll run the electrical rules check.";
      if (ctx.hasValidation)
        return `Re-running ERC on **${ctx.boardName ?? "the board"}** — comparing against the previous score of **${ctx.healthScore}/100**.`;
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
      // First line: single-sentence summary (what the strip shows)
      const boardDesc = `**${ctx.boardName ?? "Board"}**${ctx.componentCount ? ` — ${ctx.componentCount} components, ${ctx.layerCount}L` : ""}`;
      let statusLine: string;
      if (!ctx.hasValidation) {
        statusLine = `${boardDesc}. ERC not run yet — say **validate** to check for issues.`;
      } else if (ctx.hasManufacturing) {
        statusLine = `${boardDesc}. Score **${ctx.healthScore}/100** — manufacturing package **ready**.`;
      } else if (ctx.activeIssueCount === 0) {
        statusLine = `${boardDesc}. Score **${ctx.healthScore}/100** — clean, ready to manufacture.`;
      } else {
        statusLine = `${boardDesc}. Score **${ctx.healthScore}/100** — ${ctx.activeIssueCount} active issue${ctx.activeIssueCount === 1 ? "" : "s"}${ctx.hasCriticals ? " including criticals" : ""}.`;
      }
      // Extended lines for the conversation drawer
      const extended: string[] = [];
      if (!ctx.hasValidation) {
        extended.push("ERC not run yet. Say **validate** to check for issues.");
      } else if (ctx.activeIssueCount === 0) {
        extended.push(`Validation: **${ctx.healthScore}/100** — no active issues.`);
      } else {
        extended.push(`Validation: **${ctx.healthScore}/100** — ${ctx.activeIssueCount} active issue${ctx.activeIssueCount === 1 ? "" : "s"}${ctx.hasCriticals ? " (critical)" : ""}.`);
      }
      if (ctx.hasManufacturing) {
        extended.push("Manufacturing package: **ready**.");
      } else if (ctx.hasValidation && !ctx.hasCriticals) {
        extended.push("Ready to manufacture — say **manufacture** to generate files.");
      }
      return [statusLine, ...extended].join("  \n");
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
        "**what's next** — I'll tell you the single most important action",
        "**open board** — inspect components and layers",
        "**acknowledge warnings** — dismiss all non-critical issues",
        "**undo** — undo the last action (or Ctrl+Z)",
        "**clear** — reset the workspace",
        "Or drop a `.kicad_pcb` file directly onto the canvas.",
      ].join("  \n");

    case "next": {
      if (!ctx.hasBoardNode)
        return "Drop a `.kicad_pcb` file on the canvas to get started.";
      if (!ctx.hasValidation)
        return `Run **validate** — I need to check **${ctx.boardName ?? "the board"}** for electrical rule violations before it can go to manufacture.`;
      if (ctx.hasCriticals)
        return `Resolve the **${ctx.activeIssueCount} critical issue${ctx.activeIssueCount === 1 ? "" : "s"}** in **${ctx.boardName ?? "the board"}** — say **show issues** to review the suggested fixes.`;
      if (ctx.activeIssueCount > 0)
        return `**${ctx.activeIssueCount} non-critical issue${ctx.activeIssueCount === 1 ? "" : "s"}** remain. Say **acknowledge warnings** to dismiss them, then **manufacture** to generate the files.`;
      if (!ctx.hasManufacturing)
        return `Board is clean (score **${ctx.healthScore}/100**) — say **manufacture** to generate Gerbers, BOM, and assembly guide.`;
      return `You're done. **${ctx.boardName ?? "The board"}** is validated and packaged — manufacturing files are ready to download.`;
    }

    case "open_board":
      if (!ctx.hasBoardNode)
        return "No board on the canvas yet. Drop a `.kicad_pcb` file first.";
      return `Opening board details for **${ctx.boardName ?? "the board"}**…`;

    case "open_mfg":
      if (!ctx.hasManufacturing)
        return ctx.hasValidation && !ctx.hasCriticals
          ? `Manufacturing package not generated yet — say **manufacture** to create it.`
          : `Run **validate** first, then say **manufacture** to generate the package.`;
      return `Opening manufacturing package for **${ctx.boardName ?? "the board"}**…`;

    default: {
      const { text } = intent as { type: "unknown"; text: string };
      const t = text.toLowerCase();

      if (!ctx.hasBoardNode)
        return text
          ? `I heard you — but I need a board to work with first. Drop a \`.kicad_pcb\` file on the canvas.`
          : "Drop a `.kicad_pcb` file on the canvas or describe what you want to build.";

      // Fab ordering questions
      if (/\bjlcpcb|pcbway|oshpark|osh\s+park|fab\s+house|fabricat|order|prototype|spin\s+(the\s+)?board\b/.test(t)) {
        if (ctx.hasCriticals)
          return `**${ctx.boardName}** has critical issues — most fabs (JLCPCB, PCBWay) will reject this board. Resolve the ${ctx.activeIssueCount} active issue${ctx.activeIssueCount === 1 ? "" : "s"} first, then say **manufacture**.`;
        if (!ctx.hasValidation)
          return `Run **validate** first. I need to confirm there are no critical issues before you send it to fab.`;
        if (!ctx.hasManufacturing)
          return `**${ctx.boardName}** looks clean — score **${ctx.healthScore}/100** with no critical blockers. Say **manufacture** to generate the Gerber package, then upload to JLCPCB, PCBWay, or OSH Park.`;
        return `Manufacturing package is ready. Download the Gerbers from the Manufacture tab and upload the zip to JLCPCB, PCBWay, or your preferred fab. Most accept KiCad Gerbers directly.`;
      }

      // Layer/stackup questions
      if (/\b(layer|stack.?up|impedance|controlled|4l|6l|2l)\b/.test(t) && ctx.layerCount) {
        const l = ctx.layerCount;
        const guidance =
          l === 1 ? "Single-layer boards have limited routing options — consider 2L if you need ground plane or power isolation."
          : l === 2 ? "2-layer is cost-effective for most projects. Keep GND on B.Cu as a reference plane for best EMI performance."
          : l === 4 ? "4-layer is solid for mixed-signal or power designs: signal / GND / PWR / signal stack-up is common."
          : l >= 6 ? `${l}-layer stack-up is used for high-density or controlled-impedance designs — confirm your fab's exact dielectric thicknesses.`
          : `${l} layers detected.`;
        return `**${ctx.boardName}** is a **${l}-layer** board. ${guidance}`;
      }

      // Component count / density questions
      if (/\b(component|part|density|count|how\s+many)\b/.test(t) && ctx.componentCount) {
        const c = ctx.componentCount;
        const density = c < 10 ? "minimal footprint — low cost to assemble" : c < 50 ? "standard prototype density" : c < 150 ? "high-density — expect DFM scrutiny" : "very dense — verify clearances carefully before ordering";
        return `**${ctx.boardName}** has **${c} component${c === 1 ? "" : "s"}** across **${ctx.layerCount} layer${ctx.layerCount === 1 ? "" : "s"}** — ${density}.`;
      }

      // Fix / resolve specific top issue
      if (ctx.hasValidation && ctx.topIssue) {
        if (/\b(fix|how|resolve|repair|correct|patch|address)\b/.test(t)) {
          return `To fix the top **${ctx.topIssue.severity}**: ${ctx.topIssue.fix}. Say **show issues** to see all issues with individual fix hints.`;
        }
        if (/\b(why|reason|cause|explain|what.?s the issue|describe|tell me about)\b/.test(t)) {
          return `Top issue: **${ctx.topIssue.what}**. This matters because: it's a design-rule violation that could affect board reliability or cause fab rejection. Fix: ${ctx.topIssue.fix}`;
        }
      }

      // Health score questions
      if (/\b(score|health|rating|grade|quality|how\s+(good|bad)|pass|fail)\b/.test(t) && ctx.hasValidation && ctx.healthScore != null) {
        const s = ctx.healthScore;
        const verdict = s >= 80 ? "looks good for manufacture" : s >= 60 ? "acceptable with caveats — review the active issues" : "needs attention — score below 60 suggests significant violations";
        return `Health score is **${s}/100** — ${ctx.activeIssueCount === 0 ? "no active issues" : `${ctx.activeIssueCount} active issue${ctx.activeIssueCount === 1 ? "" : "s"}`}. This ${verdict}.`;
      }

      // Net / connectivity questions
      if (/\b(net|connection|ratsnest|connect|unconnect|pin)\b/.test(t)) {
        if (ctx.hasValidation && ctx.hasCriticals)
          return `**${ctx.boardName}** has connectivity violations in the active issues — say **show issues** to review unconnected nets and pin errors.`;
        return ctx.hasValidation
          ? `No connectivity violations detected in **${ctx.boardName}** — all nets appear routed.`
          : `Say **validate** to check **${ctx.boardName}** for unconnected nets and pin errors.`;
      }

      // EMI / power / noise questions
      if (/\b(emi|emc|noise|power\s+(plane|integrity)|ground\s+plane|decoupling|bypass)\b/.test(t)) {
        const l = ctx.layerCount ?? 2;
        if (l === 1) return `Single-layer boards have no dedicated ground plane — EMI performance will be limited. Consider a 2-layer design with a GND pour on B.Cu.`;
        if (l === 2) return `For **${ctx.boardName}** (2-layer): place a solid GND copper pour on B.Cu, keep high-speed traces short, and add 100nF decoupling caps close to each IC's VCC pin.`;
        return `For **${ctx.boardName}** (${l}-layer): with dedicated ground/power planes, EMI should be well-controlled. Verify your layer stack-up has alternating signal/reference layers.`;
      }

      // Thermal / heat questions
      if (/\b(thermal|heat|temperature|dissipat|hotspot|via|copper\s+fill)\b/.test(t)) {
        return `For thermal management on **${ctx.boardName}**: use thermal vias under power components, maximize copper pour area on the GND net, and ensure components with high dissipation have adequate clearance for airflow.`;
      }

      // Clearance / trace width questions
      if (/\b(clearance|spacing|trace\s+width|minimum|rule|0\.\d+\s*mm)\b/.test(t)) {
        if (ctx.hasValidation && ctx.activeIssueCount > 0)
          return `**${ctx.boardName}** has ${ctx.activeIssueCount} active issue${ctx.activeIssueCount === 1 ? "" : "s"} — some may be clearance violations. Say **show issues** to review the specific traces and components flagged.`;
        return `For most fabs (JLCPCB, PCBWay): minimum trace width 0.127mm, minimum clearance 0.127mm, minimum drill 0.3mm. Check your fab's design rules and confirm they match your KiCad DRC settings.`;
      }

      // Generic fallbacks based on pipeline state
      if (!ctx.hasValidation)
        return `I can see **${ctx.boardName}** on the canvas. Say **validate** to run the electrical rules check, or **help** to see everything I can do.`;
      if (ctx.hasCriticals)
        return `**${ctx.boardName}** has **${ctx.activeIssueCount} critical issue${ctx.activeIssueCount === 1 ? "" : "s"}** blocking manufacture. Say **show issues** to review the fixes, or say **what's next** for guidance.`;
      if (!ctx.hasManufacturing)
        return `**${ctx.boardName}** is validated — health score **${ctx.healthScore}/100**. ${ctx.activeIssueCount === 0 ? 'Say **manufacture** to generate Gerbers and BOM.' : `${ctx.activeIssueCount} non-critical issue${ctx.activeIssueCount === 1 ? "" : "s"} remain — say **acknowledge warnings** then **manufacture**, or **show issues** to review.`}`;
      return `**${ctx.boardName}** is fully processed — validated and packaged. Manufacturing files are ready to download and submit to fab.`;
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

  validationIssues(total: number, critical: number, topFix?: string): string {
    const base = critical > 0
      ? `Found **${total} issue${total === 1 ? "" : "s"}**, including **${critical} critical**. These must be resolved before manufacture.`
      : `Found **${total} issue${total === 1 ? "" : "s"}** — no critical blockers.`;
    return topFix ? `${base} Top fix: ${topFix}` : base;
  },

  revalidationResult(newScore: number, oldScore: number, total: number, critical: number): string {
    const delta = newScore - oldScore;
    const direction = delta > 0 ? `improved **${oldScore} → ${newScore}**` : delta < 0 ? `dropped **${oldScore} → ${newScore}**` : `unchanged at **${newScore}/100**`;
    const suffix = critical > 0
      ? ` — **${critical} critical issue${critical === 1 ? "" : "s"}** still need attention.`
      : total === 0
        ? ` — board is now clean.`
        : ` — no critical blockers remaining.`;
    return `Score ${direction}${suffix}`;
  },

  schematicLoaded(filename: string): string {
    return `Schematic **${filename}** loaded. Netlist structure will be analyzed when you say **validate** or click "Analyze nets".`;
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

  criticalNudge(boardName: string, criticalCount: number): string {
    const plural = criticalCount === 1 ? "issue" : "issues";
    return `Still **${criticalCount} critical ${plural}** blocking **${boardName}**. These will cause board failure — say **show issues** to review the fixes.`;
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

  drawerOpenedBoard(boardName: string, componentCount: number, layerCount: number, netCount?: number, healthScore?: number): string {
    const specs = [`**${componentCount}** component${componentCount === 1 ? "" : "s"}`, `**${layerCount}**-layer`];
    if (netCount && netCount > 0) specs.push(`**${netCount}** nets`);
    const validation = healthScore != null
      ? ` Health score: **${healthScore}/100**.`
      : " Validation not run yet — say **validate** to check for issues.";
    return `**${boardName}** — ${specs.join(", ")}.${validation}`;
  },

  drawerOpenedValidation(boardName: string, healthScore: number, activeIssueCount: number, criticalCount: number): string {
    if (activeIssueCount === 0)
      return `**${boardName}** passed all checks — score **${healthScore}/100**, no active issues. Ready to manufacture.`;
    const criticalSuffix = criticalCount > 0
      ? ` **${criticalCount} critical** must be resolved before manufacture.`
      : ` No critical blockers — acceptable to proceed.`;
    return `**${boardName}** — score **${healthScore}/100**, ${activeIssueCount} active issue${activeIssueCount === 1 ? "" : "s"}.${criticalSuffix}`;
  },

  drawerOpenedMfg(packageName: string, status: string, gerberCount?: number, hasBom?: boolean, hasAssembly?: boolean): string {
    if (status !== "done") return `Generating **${packageName}**…`;
    const parts: string[] = [`**${gerberCount ?? 8}** Gerber/drill files`];
    if (hasBom) parts.push("BOM");
    if (hasAssembly) parts.push("assembly guide");
    return `Package ready — ${parts.join(", ")}. Download the Gerber zip and submit to your preferred fab.`;
  },

  resumeProject(boardName: string, healthScore?: number, activeIssueCount?: number, criticalCount?: number, hasMfg?: boolean): string {
    if (hasMfg)
      return `Welcome back. **${boardName}** is fully processed — manufacturing package ready to download and submit.`;
    if (healthScore != null) {
      if (activeIssueCount === 0)
        return `Welcome back. **${boardName}** is validated and clean (score **${healthScore}/100**) — ready to manufacture. Say **manufacture** to generate the files.`;
      if (criticalCount && criticalCount > 0)
        return `Welcome back. **${boardName}** has **${criticalCount} critical issue${criticalCount === 1 ? "" : "s"}** blocking manufacture (score **${healthScore}/100**). Say **show issues** to review.`;
      return `Welcome back. **${boardName}** has **${activeIssueCount} active issue${activeIssueCount === 1 ? "" : "s"}** (score **${healthScore}/100**). Say **acknowledge warnings** then **manufacture**, or **show issues** to review.`;
    }
    return `Welcome back. **${boardName}** is on the canvas. Say **validate** to run the electrical rules check.`;
  },

  drawerOpenedFile(filename: string, fileKind: string, sizeBytes: number, isParsed: boolean): string {
    const kindLabels: Record<string, string> = {
      kicad_pcb: "KiCad PCB",
      kicad_sch: "KiCad Schematic",
      gerber: "Gerber file",
      bom_csv: "BOM CSV",
      unknown: "File",
    };
    const label = kindLabels[fileKind] ?? "File";
    const size = formatFileSize(sizeBytes);
    if (isParsed) return `**${filename}** — ${label}, ${size}. Board already extracted.`;
    return `**${filename}** — ${label}, ${size}. Click **Parse board** on the canvas node to extract the circuit structure.`;
  },
};
