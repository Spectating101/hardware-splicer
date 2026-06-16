import type { BuildIntentContext, BuildToolInvocation, BuildToolName } from "@/lib/jarvis/build-agent";
import { detectBuildToolInvocations } from "@/lib/jarvis/build-agent";
import catalogIds from "@/lib/hardware-splicer/catalog-build-ids.json";

const SUPPORTED_BUILD_IDS = catalogIds.build_ids;
import { expandUserPhrase } from "@/lib/jarvis/phrase-expander";

export const BUILD_TOOL_CATALOG = `
Available tools (pick 0–4, in order):
- splice_recipe(buildId): load a full ready-made project. buildId one of: ${SUPPORTED_BUILD_IDS.join(", ")}
- compose_modules: pick and place parts from everyday language (temperature, motor, relay…)
- auto_wire: connect pins on what's already on the canvas
- rebuild_wires: redo all wiring from scratch
- check_design: safety + manufacturability check
- generate_firmware: download starter Arduino/MicroPython code for the current board
- open_pcb: open PCB preview
- export_kicad: download KiCad board file
- export_bom: download parts shopping list (CSV)
- manufacture: run DFM + Gerber fab pipeline
- clear_canvas: empty the board

Rules:
- "add X" on a non-empty board → compose_modules (NOT splice_recipe)
- splice_recipe only for empty board OR explicit new project
- generate_firmware when user wants code/sketch/upload/program
- check_design when asking if safe to power on
`.trim();

const VALID_TOOLS = new Set<BuildToolName>([
  "auto_wire", "rebuild_wires", "compose_modules", "splice_recipe", "check_design",
  "open_pcb", "export_kicad", "export_bom", "manufacture", "clear_canvas", "generate_firmware",
]);

export function expandAndDetectTools(
  text: string,
  ctx: BuildIntentContext = {},
): BuildToolInvocation[] {
  const expanded = expandUserPhrase(text);
  return detectBuildToolInvocations(expanded, ctx);
}

export function parseLlmToolPlan(raw: string): BuildToolInvocation[] {
  const jsonMatch = raw.match(/\{[\s\S]*\}/);
  if (!jsonMatch) return [];
  try {
    const parsed = JSON.parse(jsonMatch[0]) as { tools?: Array<{ name?: string; buildId?: string }> };
    if (!Array.isArray(parsed.tools)) return [];
    const out: BuildToolInvocation[] = [];
    for (const t of parsed.tools) {
      if (!t.name || !VALID_TOOLS.has(t.name as BuildToolName)) continue;
      out.push({
        name: t.name as BuildToolName,
        buildId: typeof t.buildId === "string" ? t.buildId : undefined,
      });
    }
    return out;
  } catch {
    return [];
  }
}

/** Prefer LLM plan when non-empty; always merge regex hits for safety-critical tools. */
export function mergeToolPlans(
  llm: BuildToolInvocation[],
  regex: BuildToolInvocation[],
): BuildToolInvocation[] {
  const merged = [...llm];
  const keys = new Set(merged.map((t) => (t.buildId ? `${t.name}:${t.buildId}` : t.name)));

  for (const r of regex) {
    const key = r.buildId ? `${r.name}:${r.buildId}` : r.name;
    if (!keys.has(key)) {
      merged.push(r);
      keys.add(key);
    }
  }

  if (merged.length === 0) return regex;
  return merged;
}

export function buildLlmPlannerPrompt(
  userText: string,
  ctx: BuildIntentContext,
): string {
  return `${BUILD_TOOL_CATALOG}

Canvas: ${ctx.moduleCount ?? 0} modules, ${ctx.wireCount ?? 0} wires.

User said: "${userText}"

Respond with ONLY JSON, no markdown:
{"tools":[{"name":"tool_name","buildId":"optional_catalog_id"}]}`;
}
