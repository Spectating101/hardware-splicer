import type { BuildGraph } from "@/lib/rules/safety-rules";
import type { BuildWarning } from "@/lib/rules/safety-rules";
import type { DrcResult } from "@/lib/pcb/drc";
import type { EngineCompileProof } from "@/lib/hardware-splicer/engine-proof";
import { findModule } from "@/lib/modules/module-library";
import { pickModulesForGoal, wantsModuleComposition } from "@/lib/jarvis/build-module-picker";
import { expandUserPhrase } from "@/lib/jarvis/phrase-expander";
import { formatManufactureJarvisSummary, type ManufactureJarvisResult } from "@/lib/jarvis/manufacture-summary";
import { suggestJarvisNextSteps } from "@/lib/jarvis/next-steps";
import catalogIds from "@/lib/hardware-splicer/catalog-build-ids.json";

export type BuildToolName =
  | "auto_wire"
  | "rebuild_wires"
  | "compose_modules"
  | "splice_recipe"
  | "check_design"
  | "generate_firmware"
  | "open_pcb"
  | "export_kicad"
  | "export_bom"
  | "manufacture"
  | "clear_canvas";

export const SUPPORTED_BUILD_IDS: string[] = catalogIds.build_ids;

export interface BuildToolInvocation {
  name: BuildToolName;
  buildId?: string;
}

export type BuildToolResult =
  | { tool: "auto_wire"; ok: boolean; added: number; wireCount: number; detail: string }
  | { tool: "rebuild_wires"; ok: boolean; added: number; wireCount: number; detail: string }
  | { tool: "check_design"; safetyErrors: number; safetyWarns: number; drcPass: boolean; drcErrors: number; drcWarnings: number; detail: string }
  | { tool: "open_pcb"; ok: boolean; detail: string }
  | { tool: "export_kicad"; ok: boolean; detail: string }
  | { tool: "export_bom"; ok: boolean; detail: string }
  | { tool: "manufacture"; ok: boolean; detail: string; manufacturingReady?: boolean; blockers?: string[] }
  | { tool: "splice_recipe"; ok: boolean; buildId: string; moduleCount: number; wireCount: number; detail: string }
  | { tool: "compose_modules"; ok: boolean; added: number; moduleIds: string[]; hints: string[]; detail: string }
  | { tool: "clear_canvas"; ok: boolean; detail: string }
  | { tool: "generate_firmware"; ok: boolean; filename: string; buildId: string; detail: string };

export interface BuildJarvisSnapshot {
  moduleCount: number;
  wireCount: number;
  modules: Array<{ nodeId: string; moduleId: string; label: string; category: string }>;
  wires: Array<{ from: string; to: string }>;
  safety: { errors: number; warns: number; infos: number; messages: string[] };
  drc: { pass: boolean; errors: number; warnings: number; messages: string[] };
}

export interface BuildJarvisHandlers {
  autoWire(): Promise<{ added: number; wireCount: number; detail: string; snapshot?: BuildJarvisSnapshot }>;
  rebuildWires(): Promise<{ added: number; wireCount: number; detail: string; snapshot?: BuildJarvisSnapshot }>;
  spliceRecipe(buildId: string): Promise<{ ok: boolean; buildId: string; moduleCount: number; wireCount: number; detail: string; snapshot?: BuildJarvisSnapshot }>;
  composeModules(userText: string): Promise<{ ok: boolean; added: number; moduleIds: string[]; hints: string[]; detail: string; snapshot?: BuildJarvisSnapshot }>;
  clearCanvas(): void;
  openPcb(): void;
  exportKicad(): void;
  exportBom(): void;
  manufacture(): Promise<ManufactureJarvisResult>;
  generateFirmware(): { ok: boolean; filename: string; buildId: string; detail: string };
}

export interface BuildIntentContext {
  moduleCount?: number;
  wireCount?: number;
}

/** Normie / functional language → catalog build (mirrors DIY profile library). */
const FUNCTION_TO_BUILD: Array<{ buildId: string; patterns: RegExp[] }> = [
  {
    buildId: "automatic_plant_watering",
    patterns: [
      /water(?:ing)? my plants?/,
      /keep (?:my )?plants? watered/,
      /when (?:the )?soil(?:'s| is) dry/,
      /auto(?:matic(?:ally)?)? water/,
      /plant(?:s)? (?:need|get) water/,
      /irrigation/,
      /water the herbs?/,
      /moisture.*pump|pump.*when.*dry/,
      /indoor plant care/,
      /plant bot/,
      /smart agriculture/,
      /water my (?:herbs?|garden|pots?)/,
      /droplet|esphome.*irrigation/,
    ],
  },
  {
    buildId: "sensor_logger",
    patterns: [
      /log (?:the )?temp/,
      /track (?:the )?temp/,
      /monitor (?:the )?(?:temp|humidity|room)/,
      /temperature (?:and|&) humidity/,
      /environment(?:al)? monitor/,
      /data logger/,
      /tell me when (?:it'?s|the room is) (?:hot|cold|humid)/,
      /sensor that (?:logs|records|measures)/,
      /multi.?sensor.*(?:display|receiver)/,
      /room climate/,
      /thingspeak|firebase.*sensor/,
    ],
  },
  {
    buildId: "room_display_station",
    patterns: [
      /room (?:temp|temperature).*(?:screen|display)/,
      /(?:temp|temperature).*(?:on|to) (?:a |the )?(?:small )?(?:screen|display)/,
      /color (?:tft|touchscreen|display)/,
      /cheap yellow display|cyd\b/,
      /show (?:room )?(?:temp|readings?) on (?:a )?screen/,
      /weather (?:on|with) (?:a )?display/,
      /dashboard (?:with|on) (?:a )?screen/,
    ],
  },
  {
    buildId: "usb_fume_extractor",
    patterns: [
      /solder(?:ing)? fan/,
      /fume(?:s)? extractor/,
      /bench fan/,
      /desk fan/,
      /blow(?: away)? smoke/,
      /solder smoke/,
      /smoke.*stink/,
      /stink.*solder/,
      /vent(?:ilation)? at my desk/,
      /cool(?:ing)? (?:my )?desk/,
      /stinks when i solder/,
    ],
  },
  {
    buildId: "robot_drive_base",
    patterns: [
      /little robot/,
      /robot (?:car|that drives|wheels)/,
      /rover/,
      /rc car/,
      /drive around/,
      /mobile robot/,
      /motors? (?:on|for) wheels/,
    ],
  },
  {
    buildId: "smart_relay_box",
    patterns: [
      /switch (?:on|off) (?:a |the )?(?:lamp|light|outlet|heater|load)/,
      /turn (?:on|off) (?:my |the )?(?:lamp|light|fan|outlet)/,
      /relay/,
      /remote switch/,
      /control (?:a |the )?load/,
      /smart (?:outlet|switch)/,
    ],
  },
  {
    buildId: "bench_power_adapter",
    patterns: [
      /power (?:my )?projects? from/,
      /bench power/,
      /break out (?:wall|barrel|dc) power/,
      /safer power supply/,
      /power adapter/,
      /regulated (?:5v|12v|3\.3v)/,
    ],
  },
  {
    buildId: "low_voltage_motor_test_jig",
    patterns: [
      /test (?:a |my )?motor/,
      /spin (?:a |the )?motor/,
      /motor bench/,
      /check if (?:the )?motor works/,
      /servo test/,
    ],
  },
  {
    buildId: "plotter_motion_stage",
    patterns: [
      /pen plotter/,
      /draw (?:pictures|shapes) with (?:motors|steppers)/,
      /cnc (?:draw|pen)/,
      /x.?y stage/,
      /motion stage/,
    ],
  },
  {
    buildId: "small_audio_amp_box",
    patterns: [
      /(?:small |tiny )?speaker/,
      /play sound/,
      /audio alert/,
      /beep when/,
      /buzzer box/,
      /amplif(?:y|ier)/,
      /make (?:it|something) (?:beep|chirp|play)/,
    ],
  },
  {
    buildId: "camera_ir_light_or_sensor_mount",
    patterns: [
      /security camera/,
      /take photos? (?:automatically|on a timer)/,
      /timelapse/,
      /webcam rig/,
      /camera (?:mount|trigger)/,
      /watch (?:the |my )?(?:door|room|garage)/,
    ],
  },
  {
    buildId: "network_status_indicator",
    patterns: [
      /wifi (?:is )?(?:up|down|working)/,
      /internet (?:status|light|indicator)/,
      /network (?:status|light)/,
      /blink when (?:wifi|internet)/,
      /is (?:my )?(?:router|internet) (?:online|working)/,
      /wifi analyzer/,
      /signal strength.*(?:wifi|display|screen)/,
      /scan (?:for )?wifi networks/,
    ],
  },
  {
    buildId: "indicator_or_task_light",
    patterns: [
      /desk light/,
      /task light/,
      /status light/,
      /indicator light/,
      /led (?:lamp|strip|indicator)/,
      /night light/,
      /cabinet light/,
    ],
  },
  {
    buildId: "inspection_motion_fixture",
    patterns: [
      /inspect(?:ion)? (?:rig|fixture|setup)/,
      /camera slider/,
      /pan.?tilt/,
      /look at (?:boards|pcbs) closely/,
      /magnif(?:y|ier) (?:arm|setup)/,
    ],
  },
  {
    buildId: "usb_uart_debug_adapter",
    patterns: [
      /serial (?:console|debug)/,
      /read (?:the )?logs? from/,
      /usb (?:to )?serial/,
      /talk to (?:the )?board over usb/,
      /firmware logs?/,
      /uart/,
    ],
  },
  {
    buildId: "salvaged_input_panel",
    patterns: [
      /macro pad/,
      /button panel/,
      /keypad/,
      /game controller/,
      /extra buttons/,
      /input panel/,
    ],
  },
  {
    buildId: "generic_low_voltage_build",
    patterns: [
      /junk (?:parts|electronics)/,
      /random (?:parts|electronics)/,
      /whatever (?:i|we) have/,
      /something (?:useful|cool) with/,
      /electronics project/,
      /microcontroller project/,
      /low voltage (?:thing|project|build)/,
    ],
  },
];

const PROJECT_INTENT = /(?:^|\b)(?:i want|i need|help me|can you|could you|make me|build me|set up|create|design|something that|that can|so (?:my|the)|for my|project to|idea for|trying to)\b/i;

const WIRE_INTENT = /(?:wire|connect|hook(?:\s+up)?|link|join|plug(?:\s+in)?|make (?:it|this|them) work|get (?:it|this) working|put (?:it|this) together|finish (?:the )?wiring|complete the circuit|tie (?:it|them) together)/i;

const REBUILD_INTENT = /(?:rebuild|redo|start over|try again|fix (?:the )?wir|clean up|re-?route|polish|rewire)/i;

const CHECK_INTENT = /(?:check|validate|inspect|safe|ready|good to go|will (?:this|it) work|anything wrong|blow(?:\s+up)?|burn out|am i gonna|drc)/i;

const MANUFACTURE_INTENT = /(?:manufactur|gerber|fab\b|order (?:a |the )?board|get boards? made|send to factory)/i;

const FIRMWARE_INTENT = /(?:firmware|arduino sketch|(?:write|generate|download|get) (?:the )?(?:code|software|program)|upload (?:to|code)|flash (?:the )?board|make (?:it )?run|esp32 code|micropython)/i;

const PCB_INTENT = /(?:pcb|circuit board|board look|show (?:me )?(?:the )?board|preview)/i;

export interface InferredBuild {
  buildId: string;
  score: number;
  label: string;
}

function normalizeUserText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[''`]/g, "'")
    .replace(/[""]/g, '"');
}

export function inferBuildFromFunction(text: string): InferredBuild | null {
  const t = normalizeUserText(expandUserPhrase(text));
  let best: InferredBuild | null = null;

  for (const id of SUPPORTED_BUILD_IDS) {
    const spaced = id.replace(/_/g, " ");
    if (t.includes(id) || t.includes(spaced)) {
      return { buildId: id, score: 3, label: spaced };
    }
  }

  for (const entry of FUNCTION_TO_BUILD) {
    let score = 0;
    for (const pattern of entry.patterns) {
      if (pattern.test(t)) score += 1;
    }
    if (score > 0 && (!best || score > best.score)) {
      best = {
        buildId: entry.buildId,
        score,
        label: entry.buildId.replace(/_/g, " "),
      };
    }
  }

  if (!best || best.score < 1) return null;
  return best;
}

/** @deprecated use inferBuildFromFunction */
export function detectSalvageBuildId(text: string): string | null {
  return inferBuildFromFunction(text)?.buildId ?? null;
}

const REPLACE_PROJECT_INTENT = /(?:^|\b)(?:instead|switch to|rather than|new project|start (?:a )?fresh|from scratch|replace (?:this|everything))\b/i;

function shouldUseCatalogRecipe(
  inferred: InferredBuild | null,
  text: string,
  ctx: BuildIntentContext,
): boolean {
  if (!inferred || inferred.score < 1) return false;
  if (ADD_TO_CANVAS_INTENT.test(text) && (ctx.moduleCount ?? 0) > 0) return false;
  if ((ctx.moduleCount ?? 0) === 0) return true;
  if (REPLACE_PROJECT_INTENT.test(text)) return true;
  if (PROJECT_INTENT.test(text) && inferred.score >= 2) return true;
  return false;
}

export interface ComposeWireContext extends BuildIntentContext {
  /** Modules newly placed this turn — always re-wire when > 0. */
  addingModules?: number;
}

export function wantsAutoWireAfterCompose(text: string, ctx: ComposeWireContext): boolean {
  const t = normalizeUserText(text);
  if (WIRE_INTENT.test(t)) return true;
  if (/make it work|get (?:it|this) working|put it together/.test(t)) return true;
  if ((ctx.addingModules ?? 0) > 0) return true;
  if ((ctx.moduleCount ?? 0) > 0 && (ctx.wireCount ?? 0) === 0) return true;
  return (ctx.moduleCount ?? 0) === 0;
}

const ADD_TO_CANVAS_INTENT = /(?:^|\b)(?:add|also|plus|another|include|attach|put (?:on|a)|stick (?:a|an)|drop (?:in|a))\b/i;

export function detectBuildToolInvocations(
  text: string,
  ctx: BuildIntentContext = {},
): BuildToolInvocation[] {
  const normalized = normalizeUserText(expandUserPhrase(text));
  const invocations: BuildToolInvocation[] = [];
  const inferred = inferBuildFromFunction(normalized);
  const modulePick = pickModulesForGoal(normalized);

  const addToCanvas = ADD_TO_CANVAS_INTENT.test(normalized) && modulePick.moduleIds.length > 0;
  const useCatalog = shouldUseCatalogRecipe(inferred, normalized, ctx) && !addToCanvas;
  const useCompose = !useCatalog
    && modulePick.moduleIds.length > 0
    && (
      wantsModuleComposition(normalized)
      || (ctx.moduleCount ?? 0) === 0
      || (ADD_TO_CANVAS_INTENT.test(normalized) && modulePick.hints.length > 0)
    );

  if (useCatalog && inferred) {
    invocations.push({ name: "splice_recipe", buildId: inferred.buildId });
  } else if (useCompose) {
    invocations.push({ name: "compose_modules" });
  }

  if (/clear|start over|reset|empty|scratch/.test(normalized) && /canvas|board|everything|all|slate/.test(normalized)) {
    invocations.push({ name: "clear_canvas" });
  } else if (REBUILD_INTENT.test(normalized)) {
    invocations.push({ name: "rebuild_wires" });
    if (/polish|fix|clean/.test(normalized)) invocations.push({ name: "check_design" });
  } else if (WIRE_INTENT.test(normalized) && !invocations.some((i) => i.name === "splice_recipe")) {
    invocations.push({ name: "auto_wire" });
  }

  if (MANUFACTURE_INTENT.test(normalized)) invocations.push({ name: "manufacture" });
  if (/kicad|download.*pcb|export.*pcb/.test(normalized)) invocations.push({ name: "export_kicad" });
  if (/\bbom\b|bill of materials|parts list|shopping list/.test(normalized)) invocations.push({ name: "export_bom" });
  if (PCB_INTENT.test(normalized)) invocations.push({ name: "open_pcb" });
  if (FIRMWARE_INTENT.test(normalized)) invocations.push({ name: "generate_firmware" });
  if (CHECK_INTENT.test(normalized)) invocations.push({ name: "check_design" });

  if (invocations.length === 0 && /help|what should|how do|explain|not sure/.test(normalized)) {
    invocations.push({ name: "check_design" });
  }

  // Last resort — vague everyday language still gets a useful first step.
  if (invocations.length === 0) {
    if (inferred && (ctx.moduleCount ?? 0) === 0 && inferred.score >= 1) {
      invocations.push({ name: "splice_recipe", buildId: inferred.buildId });
    } else if (modulePick.moduleIds.length > 0) {
      invocations.push({ name: "compose_modules" });
    } else if ((ctx.moduleCount ?? 0) > 0 && (ctx.wireCount ?? 0) === 0) {
      invocations.push({ name: "auto_wire" });
    } else if ((ctx.moduleCount ?? 0) > 0) {
      invocations.push({ name: "check_design" });
    }
  }

  const seen = new Set<string>();
  return invocations.filter((item) => {
    const key = item.buildId ? `${item.name}:${item.buildId}` : item.name;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function snapshotFromBuild(
  graph: BuildGraph,
  warnings: BuildWarning[],
  drc: DrcResult,
  engineProof?: EngineCompileProof | null,
): BuildJarvisSnapshot {
  const modules = graph.nodes.map((n) => {
    const spec = findModule(n.moduleId);
    return {
      nodeId: n.id,
      moduleId: n.moduleId,
      label: spec?.label ?? n.moduleId,
      category: spec?.category ?? "unknown",
    };
  });
  const wires = graph.wires.map((w) => ({
    from: `${w.from.nodeId}.${w.from.pinId}`,
    to: `${w.to.nodeId}.${w.to.pinId}`,
  }));
  const safetyMsgs = warnings
    .sort((a, b) => severityRank(a.level) - severityRank(b.level))
    .slice(0, 8)
    .map((w) => `[${w.level}] ${w.message}`);
  const drcMsgs = engineProof
    ? [
        engineProof.kicadDrcPass
          ? `[kicad] DRC clean (${engineProof.kicadDrcWarnings} warning(s))`
          : `[kicad] ${engineProof.kicadDrcErrors} DRC error(s), ${engineProof.kicadDrcWarnings} warning(s)`,
        ...engineProof.blockers.slice(0, 4).map((b) => `[engine] ${b}`),
      ]
    : drc.violations
        .filter((v) => v.severity === "error" || v.severity === "warn")
        .slice(0, 8)
        .map((v) => `[${v.severity}] ${v.message}`);

  const drcPass = engineProof ? engineProof.kicadDrcPass && engineProof.buildReady : drc.pass;
  const drcErrors = engineProof ? engineProof.kicadDrcErrors : drc.summary.errors;
  const drcWarnings = engineProof ? engineProof.kicadDrcWarnings : drc.summary.warnings;

  return {
    moduleCount: graph.nodes.length,
    wireCount: graph.wires.length,
    modules,
    wires,
    safety: {
      errors: warnings.filter((w) => w.level === "error").length,
      warns: warnings.filter((w) => w.level === "warn").length,
      infos: warnings.filter((w) => w.level === "info").length,
      messages: safetyMsgs,
    },
    drc: {
      pass: drcPass,
      errors: drcErrors,
      warnings: drcWarnings,
      messages: drcMsgs,
    },
  };
}

function severityRank(level: BuildWarning["level"]): number {
  if (level === "error") return 0;
  if (level === "warn") return 1;
  return 2;
}

export async function runBuildTools(
  userText: string,
  invocations: BuildToolInvocation[],
  handlers: BuildJarvisHandlers,
  getSnapshot: () => BuildJarvisSnapshot,
): Promise<{ results: BuildToolResult[]; snapshot?: BuildJarvisSnapshot }> {
  const results: BuildToolResult[] = [];
  let snapshot: BuildJarvisSnapshot | undefined;
  for (const { name, buildId } of invocations) {
    switch (name) {
      case "auto_wire": {
        const r = await handlers.autoWire();
        if (r.snapshot) snapshot = r.snapshot;
        results.push({
          tool: "auto_wire",
          ok: r.added > 0 || r.wireCount > 0,
          added: r.added,
          wireCount: r.wireCount,
          detail: r.detail,
        });
        break;
      }
      case "rebuild_wires": {
        const r = await handlers.rebuildWires();
        if (r.snapshot) snapshot = r.snapshot;
        results.push({
          tool: "rebuild_wires",
          ok: r.wireCount > 0,
          added: r.added,
          wireCount: r.wireCount,
          detail: r.detail,
        });
        break;
      }
      case "check_design": {
        const snap = getSnapshot();
        results.push({
          tool: "check_design",
          safetyErrors: snap.safety.errors,
          safetyWarns: snap.safety.warns,
          drcPass: snap.drc.pass,
          drcErrors: snap.drc.errors,
          drcWarnings: snap.drc.warnings,
          detail: `Safety: ${snap.safety.errors} error(s), ${snap.safety.warns} warn(s). DRC: ${
            snap.drc.pass ? "manufacturable" : "blocked"
          } (${snap.drc.errors} error(s), ${snap.drc.warnings} warn(s)).`,
        });
        break;
      }
      case "open_pcb":
        handlers.openPcb();
        results.push({ tool: "open_pcb", ok: true, detail: "Opened PCB preview." });
        break;
      case "export_kicad":
        handlers.exportKicad();
        results.push({ tool: "export_kicad", ok: true, detail: "Downloaded KiCad .kicad_pcb." });
        break;
      case "export_bom":
        handlers.exportBom();
        results.push({ tool: "export_bom", ok: true, detail: "Downloaded BOM CSV." });
        break;
      case "manufacture": {
        const mfg = await handlers.manufacture();
        results.push({
          tool: "manufacture",
          ok: mfg.ok,
          detail: mfg.detail,
          manufacturingReady: mfg.manufacturingReady,
          blockers: mfg.blockers,
        });
        break;
      }
      case "splice_recipe": {
        if (!buildId) {
          results.push({
            tool: "splice_recipe",
            ok: false,
            buildId: "",
            moduleCount: 0,
            wireCount: 0,
            detail: "Tell me what you want it to do — water plants, log temperature, drive a robot, etc.",
          });
          break;
        }
        const r = await handlers.spliceRecipe(buildId);
        if (r.snapshot) snapshot = r.snapshot;
        results.push({
          tool: "splice_recipe",
          ok: r.ok,
          buildId: r.buildId,
          moduleCount: r.moduleCount,
          wireCount: r.wireCount,
          detail: r.detail,
        });
        break;
      }
      case "compose_modules": {
        const r = await handlers.composeModules(userText);
        if (r.snapshot) snapshot = r.snapshot;
        results.push({
          tool: "compose_modules",
          ok: r.ok,
          added: r.added,
          moduleIds: r.moduleIds,
          hints: r.hints,
          detail: r.detail,
        });
        break;
      }
      case "clear_canvas":
        handlers.clearCanvas();
        results.push({ tool: "clear_canvas", ok: true, detail: "Cleared the canvas." });
        break;
      case "generate_firmware": {
        const r = handlers.generateFirmware();
        results.push({
          tool: "generate_firmware",
          ok: r.ok,
          filename: r.filename,
          buildId: r.buildId,
          detail: r.detail,
        });
        break;
      }
      default:
        break;
    }
  }
  return { results, snapshot };
}

function friendlyBuildLabel(buildId: string): string {
  return buildId.replace(/_/g, " ");
}

/** Guidance when no tools matched — still plain and actionable. */
export function buildUnmatchedUserGuidance(
  text: string,
  snapshot: BuildJarvisSnapshot,
): string {
  const inferred = inferBuildFromFunction(text);
  const pick = pickModulesForGoal(text);

  if (snapshot.moduleCount === 0) {
    if (inferred) {
      return `It sounds like you want "${friendlyBuildLabel(inferred.buildId)}". Say "yes, build that" and I'll place the parts and wire them up.`;
    }
    if (pick.hints.length > 0) {
      return `I think you're talking about ${pick.hints.join(" and ")}. Describe it in one sentence — like "room temperature on a small screen" — and I'll set it up.`;
    }
    return "Tell me what you want it to do in everyday words — for example \"water my plants when the soil is dry\" or \"is it safe to plug in?\"";
  }

  if (snapshot.wireCount === 0) {
    return "Parts are on the board but nothing is wired yet. Say \"hook it up\" or \"make it work\" and I'll connect them.";
  }

  return "You can ask: \"is it safe to plug in?\", \"write the code for this board\", or \"get the shopping list\".";
}

/** Plain-English summary when tools ran — shown immediately and used as LLM fallback. */
export function formatBuildToolSummary(
  results: BuildToolResult[],
  snapshot: BuildJarvisSnapshot,
): string {
  if (results.length === 0) return "";

  const lines: string[] = [];
  for (const r of results) {
    switch (r.tool) {
      case "splice_recipe":
        lines.push(
          r.ok
            ? `Done — I laid out a "${friendlyBuildLabel(r.buildId)}" project with ${r.moduleCount} parts and ${r.wireCount} connections.`
            : r.detail,
        );
        break;
      case "compose_modules":
        lines.push(
          r.ok
            ? r.detail
            : r.detail,
        );
        break;
      case "auto_wire":
        lines.push(
          r.ok
            ? r.detail
            : "I couldn't find matching pin connections for these parts. Try \"rebuild the wiring\" or describe what's missing.",
        );
        break;
      case "rebuild_wires":
        lines.push(r.ok ? r.detail : "Couldn't rebuild wiring — double-check that each part is something I recognize.");
        break;
      case "check_design": {
        const safe = r.safetyErrors === 0;
        const drc = r.drcPass;
        if (snapshot.moduleCount === 0) {
          lines.push("The breadboard is empty — tell me what you'd like to build and I'll pick parts for you.");
        } else if (safe && drc) {
          lines.push(
            "Looks good from here — no safety blockers, and the board layout is clean enough to manufacture. Still double-check wire colors and +/− before you plug in.",
          );
        } else if (!safe) {
          lines.push(
            `Please fix ${r.safetyErrors} safety issue(s) before powering on — I explain the first ones below.`,
          );
        } else {
          lines.push(
            `Wiring looks okay for a bench test, but fix ${r.drcErrors} board-layout issue(s) before ordering PCBs.`,
          );
        }
        break;
      }
      case "open_pcb":
        lines.push("Opened the circuit-board preview — you can see how it would look manufactured.");
        break;
      case "export_kicad":
        lines.push("Downloaded the KiCad board file — open it in KiCad if you want to tweak the layout.");
        break;
      case "export_bom":
        lines.push("Downloaded your shopping list (BOM) — that's the parts to buy.");
        break;
      case "manufacture":
        lines.push(r.detail);
        break;
      case "clear_canvas":
        lines.push("Cleared the board — we're starting fresh.");
        break;
      case "generate_firmware":
        lines.push(
          r.ok
            ? r.detail
            : r.detail,
        );
        break;
      default:
        break;
    }
  }

  if (snapshot.safety.errors > 0) {
    const plain = snapshot.safety.messages
      .slice(0, 2)
      .map((m) => m.replace(/^\[(error|warn|info)\]\s*/i, ""));
    lines.push(`Safety note: ${plain.join(" ")}`);
  } else if (snapshot.wireCount > 0 && snapshot.drc.pass && !results.some((r) => r.tool === "check_design")) {
    lines.push("Power, ground, and signal lines are connected.");
  }

  const next = suggestJarvisNextSteps(results, snapshot);
  if (next) lines.push(next);

  return lines.join("\n\n");
}

export { formatManufactureJarvisSummary };

export function buildJarvisContextString(
  snapshot: BuildJarvisSnapshot,
  toolResults: BuildToolResult[],
  userText?: string,
): string {
  const actions = toolResults.length
    ? JSON.stringify(toolResults, null, 2)
    : "(none — conversational turn only)";
  const inferred = userText ? inferBuildFromFunction(userText) : null;
  const modulePick = userText ? pickModulesForGoal(userText) : null;

  return `JARVIS_BUILD_CANVAS_CONTEXT
You are Jarvis on Circuit.AI's /build breadboard — the ONLY control surface.
Users speak in plain everyday language about what they want something to DO, not part numbers.
Tools may have ALREADY RUN before you reply. Summarize outcomes simply.

USER_MESSAGE: ${userText ?? "(n/a)"}
INFERRED_GOAL: ${inferred ? `${inferred.label} (${inferred.buildId}, confidence ${inferred.score})` : "none"}
INFERRED_PARTS: ${modulePick && modulePick.moduleIds.length ? JSON.stringify({ hints: modulePick.hints, modules: modulePick.labels }) : "none"}

ACTIONS_THIS_TURN:
${actions}

CANVAS_STATE:
- modules: ${snapshot.moduleCount}
- wires: ${snapshot.wireCount}
- modules_json: ${JSON.stringify(snapshot.modules)}
- wires_json: ${JSON.stringify(snapshot.wires)}
- safety_errors: ${snapshot.safety.errors}
- safety_warns: ${snapshot.safety.warns}
- safety_infos: ${snapshot.safety.infos}
- safety_messages: ${JSON.stringify(snapshot.safety.messages)}
- drc_pass: ${snapshot.drc.pass}
- drc_errors: ${snapshot.drc.errors}
- drc_warnings: ${snapshot.drc.warnings}
- drc_messages: ${JSON.stringify(snapshot.drc.messages)}

Rules:
- Mirror the user's goal in their own words (water plants, desk fan, etc.) — not catalog jargon unless helpful.
- Anchor answers in the modules and wires above — do not invent parts.
- If wiring ran, explain power, ground, and control in plain language.
- If safety or DRC issues exist, say what to fix before plugging in.
- Keep responses tight: 3–8 sentences unless they asked for a walkthrough.`.trim();
}
