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
  /** Up to 3 component refs of the most severe active issues — surfaced as
   *  chip tokens `[ref:X]` so users can click into the canvas from chat. */
  topIssueRefs?: string[];
  /** Currently selected component (if any) — lets responses address it by name. */
  selectedRef?: string;
}

const PROJECT_ACTION_TOKENS = new Set([
  "assemble",
  "build",
  "create",
  "diy",
  "engineer",
  "help",
  "make",
  "need",
  "prototype",
  "solve",
  "want",
]);

const HARDWARE_CONTEXT_TOKENS = new Set([
  "adapter",
  "adapters",
  "arduino",
  "audio",
  "board",
  "boards",
  "budget",
  "buzzer",
  "camera",
  "capture",
  "cheap",
  "circuit",
  "cooling",
  "device",
  "electronics",
  "esp32",
  "fan",
  "fans",
  "hardware",
  "hot",
  "humidity",
  "image",
  "indicator",
  "internet",
  "irrigation",
  "junk",
  "keypad",
  "lamp",
  "led",
  "leds",
  "light",
  "module",
  "modules",
  "moisture",
  "motor",
  "mosfet",
  "network",
  "parts",
  "pcb",
  "photo",
  "plant",
  "plants",
  "pump",
  "random",
  "robot",
  "router",
  "rover",
  "salvage",
  "sensor",
  "solenoid",
  "speaker",
  "spare",
  "splice",
  "smoke",
  "system",
  "switches",
  "temperature",
  "thing",
  "tool",
  "trigger",
  "usb",
  "valve",
  "water",
  "watering",
  "wheel",
  "wheels",
  "wifi",
  "wires",
]);

function wordTokens(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .map((token) => token.trim())
      .filter(Boolean),
  );
}

export function shouldRouteToDiyProjectPlanner(text: string): boolean {
  const tokens = wordTokens(text);
  const hasProjectAction = [...PROJECT_ACTION_TOKENS].some((token) => tokens.has(token));
  const hasHardwareContext = [...HARDWARE_CONTEXT_TOKENS].some((token) => tokens.has(token));
  return hasProjectAction && hasHardwareContext;
}

export function shouldContinueDiyProjectPlanner(text: string): boolean {
  const tokens = wordTokens(text);
  return [...HARDWARE_CONTEXT_TOKENS].some((token) => tokens.has(token));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function numberValue(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function stringList(value: unknown, limit = 5): string[] {
  return Array.isArray(value)
    ? value.flatMap((item) => {
        const text = stringValue(item);
        return text ? [text] : [];
      }).slice(0, limit)
    : [];
}

function recordList(value: unknown, limit = 5): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.flatMap((item) => isRecord(item) ? [item] : []).slice(0, limit)
    : [];
}

function humanizeId(value: string | undefined) {
  return value ? value.replace(/_/g, " ") : undefined;
}

function percentText(value: unknown): string | undefined {
  const n = numberValue(value);
  if (n === undefined) return undefined;
  return `${Math.round(n * 100)}%`;
}

export function summarizeDiyProjectPlannerResponse(payload: unknown, originalPrompt: string): string {
  const root = isRecord(payload) ? payload : {};
  const plan = isRecord(root.diy_project_engineering) ? root.diy_project_engineering : root;
  const session = isRecord(root.diy_project_session) ? root.diy_project_session : {};
  const intake = isRecord(session.intake_state) ? session.intake_state : {};
  if (!isRecord(plan) || plan.available === false) {
    return [
      "I can treat that as a DIY hardware build, but I need a clearer target before I can make it authoritative.",
      "Give me the output behavior, available boards/modules, power source, budget, and what counts as pass/fail.",
    ].join("  \n");
  }

  const intent = isRecord(plan.project_intent) ? plan.project_intent : {};
  const requirements = isRecord(plan.requirements) ? plan.requirements : {};
  const resourcePlan = isRecord(plan.resource_plan) ? plan.resource_plan : {};
  const coverage = isRecord(resourcePlan.coverage) ? resourcePlan.coverage : {};
  const procurement = isRecord(resourcePlan.procurement) ? resourcePlan.procurement : {};
  const readiness = isRecord(plan.readiness) ? plan.readiness : {};

  const label =
    stringValue(intent.profile_label) ??
    humanizeId(stringValue(intent.profile_id)) ??
    originalPrompt;
  const readinessLevel = humanizeId(stringValue(readiness.level)) ?? "evidence gated";
  const readinessScore = percentText(readiness.score);
  const coverageScore = percentText(coverage.coverage_score);
  const missing = stringList(coverage.missing_capabilities, 4);
  const selected = recordList(resourcePlan.selected_resources, 5)
    .map((resource) => stringValue(resource.name) ?? stringValue(resource.resource_id))
    .filter((name): name is string => !!name);
  const blocks = recordList(plan.architecture_blocks, 6)
    .map((block) => stringValue(block.block_id))
    .filter((id): id is string => !!id)
    .map(humanizeId)
    .filter((id): id is string => !!id);
  const gates = recordList(plan.engineering_gates, 3)
    .map((gate) => stringValue(gate.prompt))
    .filter((prompt): prompt is string => !!prompt);
  const actions = stringList(plan.next_actions, 3);
  const capabilities = stringList(requirements.required_capabilities, 6).map(humanizeId).filter((v): v is string => !!v);
  const estimatedCost = numberValue(procurement.estimated_cost_usd);
  const budget = numberValue(procurement.budget_usd);
  const withinBudget = procurement.within_budget;
  const canPower = readiness.can_build_or_power_now === true;
  const capturedResources = recordList(intake.available_resources, 5)
    .map((resource) => stringValue(resource.name) ?? stringValue(resource.resource_id))
    .filter((name): name is string => !!name);
  const absentResources = recordList(intake.known_absent_resources, 4)
    .map((resource) => stringValue(resource.name) ?? stringValue(resource.resource_id))
    .filter((name): name is string => !!name);
  const turnCount = isRecord(session.conversation) ? numberValue(session.conversation.turn_count) : undefined;

  const lines = [
    `I can ${turnCount && turnCount > 1 ? "update" : "start"} this as a real build plan: **${label}**.`,
    `Readiness: **${readinessLevel}**${readinessScore ? ` (${readinessScore})` : ""}. Coverage: **${coverageScore ?? "unknown"}**${missing.length ? `; missing ${missing.map(humanizeId).join(", ")}.` : "; no required capability gaps reported."}`,
  ];

  if (capturedResources.length || absentResources.length) {
    const captured = capturedResources.length ? `Captured inventory: ${capturedResources.join(", ")}.` : "";
    const absent = absentResources.length ? ` Not currently available: ${absentResources.join(", ")}.` : "";
    lines.push(`${captured}${absent}`);
  }
  if (capabilities.length) {
    lines.push(`Required capabilities: ${capabilities.join(", ")}.`);
  }
  if (blocks.length) {
    lines.push(`Architecture path: ${blocks.join(" -> ")}.`);
  }
  if (selected.length || estimatedCost !== undefined) {
    const cost = estimatedCost !== undefined ? ` Estimated buy gap: **$${estimatedCost.toFixed(2)}**.` : "";
    const budgetNote = budget !== undefined
      ? withinBudget === false
        ? ` Budget target: **$${budget.toFixed(2)}**, so this needs reuse, cheaper substitutes, or scope reduction.`
        : ` Budget target: **$${budget.toFixed(2)}**.`
      : "";
    lines.push(`Resources to review first: ${selected.length ? selected.join(", ") : "none selected yet"}.${cost}${budgetNote}`);
  }
  if (gates.length) {
    lines.push(`First proof gate: ${gates[0]}`);
  }
  if (actions.length) {
    lines.push(`Next action: ${actions[0]}`);
  }
  lines.push(
    canPower
      ? "Power-up is allowed by the planner, but still use current limiting and no-short checks."
      : "Do not power it yet; close the evidence gates first: pass/fail behavior, block diagram, no-short checks, polarity, and current budget.",
  );
  lines.push("To continue, tell me the parts actually in the junk pile, any labels/ratings on the power source, and the hard budget ceiling.");

  return lines.join("  \n");
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
      {
        const chipList = (ctx.topIssueRefs ?? [])
          .slice(0, 3)
          .map((r) => `[ref:${r}]`)
          .join(" ");
        const suffix = chipList ? ` Flagged: ${chipList}.` : "";
        return `Opening the issues panel — ${ctx.activeIssueCount} active issue${ctx.activeIssueCount === 1 ? "" : "s"} found.${suffix}`;
      }

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
        "**describe a build** — turn a DIY hardware goal into architecture, resources, proof gates, and next action",
        "**validate** — run ERC and DFM check on the board",
        "**manufacture** — generate Gerbers, BOM, and assembly guide",
        "**show issues** — open the validation panel",
        "**status** — project summary",
        "**what's next** — I'll tell you the single most important action",
        "**open board** — inspect components and layers",
        "**acknowledge warnings** — dismiss all non-critical issues",
        "**undo** — undo the last action (or Ctrl+Z)",
        "**clear** — reset the workspace",
        "Drop a `.kicad_pcb` file for board validation, or describe what you want to build from modules/components.",
      ].join("  \n");

    case "next": {
      if (!ctx.hasBoardNode)
        return "Drop a `.kicad_pcb` file on the canvas to get started.";
      if (!ctx.hasValidation)
        return `Run **validate** — I need to check **${ctx.boardName ?? "the board"}** for electrical rule violations before it can go to manufacture.`;
      if (ctx.hasCriticals) {
        const refs = (ctx.topIssueRefs ?? []).slice(0, 3).map((r) => `[ref:${r}]`).join(" ");
        const list = refs ? ` Start with ${refs}.` : "";
        return `Resolve the **${ctx.activeIssueCount} critical issue${ctx.activeIssueCount === 1 ? "" : "s"}** in **${ctx.boardName ?? "the board"}** — say **show issues** to review the suggested fixes.${list}`;
      }
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
          ? `I heard you. If this is a new hardware build, describe the target function, available parts, power source, and pass/fail behavior. If it is an existing PCB, drop a \`.kicad_pcb\` file on the canvas.`
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

      // Conversational / social responses
      if (/^(hi|hello|hey|yo|sup|greetings|howdy|good\s+(morning|evening|afternoon|day))\b/.test(t)) {
        if (!ctx.hasBoardNode)
          return `Hey! I'm JARVIS — your PCB-to-manufacture AI. Drop a \`.kicad_pcb\` file to get started, or say **help** to see what I can do.`;
        if (!ctx.hasValidation)
          return `Hey! **${ctx.boardName}** is on the canvas. Say **validate** to run the electrical rules check.`;
        if (ctx.hasManufacturing)
          return `Hey! **${ctx.boardName}** is fully processed — manufacturing package ready to submit.`;
        return `Hey! **${ctx.boardName}** is at **${ctx.healthScore}/100**${ctx.hasCriticals ? ` with ${ctx.activeIssueCount} critical issue${ctx.activeIssueCount === 1 ? "" : "s"} blocking manufacture` : ctx.activeIssueCount > 0 ? ` with ${ctx.activeIssueCount} non-critical issue${ctx.activeIssueCount === 1 ? "" : "s"}` : " — clean"}. Say **what's next** for my recommendation.`;
      }

      if (/\b(thanks?|thank\s+you|cheers|great(\s+job)?|nice(\s+work)?|perfect|awesome|excellent|brilliant|love\s+it)\b/.test(t)) {
        if (ctx.hasManufacturing) return `Package is ready — good luck with the fab run. JLCPCB and PCBWay both accept this format directly.`;
        return `Anytime. Say **what's next** if you need guidance on the next step.`;
      }

      if (/\b(who\s+are\s+you|what\s+are\s+you|what\s+do\s+you\s+do|tell\s+me\s+about\s+yourself)\b/.test(t))
        return `I'm **JARVIS** — an AI built to guide you from PCB file to manufactured board. Drop a \`.kicad_pcb\`, and I'll parse it, validate it, generate Gerbers, and tell you exactly where to send it for manufacture.`;

      // Beginner explanations
      if (/what\s+is\s+a?\s*gerber|gerber\s+file\s*\?/.test(t))
        return `**Gerber files** are the standard format that PCB manufacturers use to produce your board. They describe each copper layer, silkscreen, solder mask, and drill positions as separate files. I generate them from your KiCad design when you say **manufacture**.`;

      if (/what\s+is\s+a?\s*bom|bill\s+of\s+material/.test(t))
        return `**BOM (Bill of Materials)** is the list of all components needed to populate your PCB — reference designators (R1, C3, U1), values (10kΩ, 100nF), and footprints. I export it as a CSV when you generate the manufacturing package.`;

      if (/what\s+is\s+(erc|drc|electrical\s+rules?\s+check|design\s+rules?\s+check)/.test(t))
        return `**ERC (Electrical Rules Check)** verifies your schematic netlist — unconnected pins, missing power, duplicate references. **DRC (Design Rules Check)** validates the physical layout — trace clearances, via sizes, silk-to-copper gaps. I run both when you say **validate**.`;

      if (/what\s+is\s+a?\s*(pcb|printed\s+circuit\s+board)/.test(t))
        return `A **PCB (Printed Circuit Board)** is the physical board that connects and holds electronic components via copper traces. Your \`.kicad_pcb\` file describes its layers, copper routing, component positions, and drill holes. I validate the design and generate the files needed to manufacture it.`;

      if (/what\s+is\s+(jlcpcb|pcbway|oshpark|fab\s+house)/.test(t))
        return `**PCB fab houses** are factories that manufacture PCBs from Gerber files. **JLCPCB** and **PCBWay** are popular budget-friendly options (5 prototype boards from ~$2-5). **OSH Park** is a US-based option known for quality purple solder mask. Once I generate the manufacturing package, you upload the Gerber zip to your preferred fab.`;

      if (/what\s+is\s+a?\s*(solder\s+mask|silkscreen|copper\s+pour|ground\s+plane|via|annular|pad)/.test(t)) {
        if (/solder\s+mask/.test(t)) return `**Solder mask** is the protective coating (usually green, but any color) that covers copper traces, leaving only the pads exposed for soldering. It prevents accidental shorts and oxidation.`;
        if (/silkscreen/.test(t)) return `**Silkscreen** is the printed layer on a PCB showing component outlines, reference designators (R1, C3), polarity marks, and other labels. It's purely for assembly reference — not electrically functional.`;
        if (/copper\s+pour|ground\s+plane/.test(t)) return `A **copper pour** (or ground plane) is a filled area of copper on a layer, usually connected to GND. It improves EMI performance, provides a low-impedance return path, and helps with thermal dissipation.`;
        if (/via/.test(t)) return `A **via** is a drilled and plated hole that connects copper traces on different PCB layers. Vias cost fab money (drill time) and consume space — use them to route signals between layers or connect to an inner ground plane.`;
        if (/pad/.test(t)) return `A **pad** is the exposed copper area on a PCB where a component pin is soldered. Through-hole pads have drilled holes; SMD (surface-mount) pads are flat copper areas on the surface layer.`;
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

  drawerOpenedBoard(boardName: string, componentCount: number, layerCount: number, netCount?: number, healthScore?: number, widthMm?: number, heightMm?: number): string {
    const specs = [`**${componentCount}** component${componentCount === 1 ? "" : "s"}`, `**${layerCount}**-layer`];
    if (netCount && netCount > 0) specs.push(`**${netCount}** nets`);
    if (widthMm != null && heightMm != null) specs.push(`~${Math.round(widthMm)}×${Math.round(heightMm)}mm`);
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
