import type { BuildJarvisSnapshot, BuildToolResult } from "@/lib/jarvis/build-agent";

/** One plain-language suggestion for what to say next. */
export function suggestJarvisNextSteps(
  results: BuildToolResult[],
  snapshot: BuildJarvisSnapshot,
): string | null {
  if (snapshot.moduleCount === 0) {
    return 'Try: "water my plants when the soil is dry" or "room temp on a small screen".';
  }

  const ran = new Set(results.map((r) => r.tool));

  if (snapshot.wireCount === 0 && !ran.has("auto_wire") && !ran.has("rebuild_wires")) {
    return 'Next, say "hook it up" or "make it work" so I can wire the parts.';
  }

  if (snapshot.wireCount > 0 && !ran.has("check_design") && snapshot.safety.errors === 0) {
    return 'Next, ask "is it safe to plug in?" before you power it on.';
  }

  if (snapshot.safety.errors > 0 && !ran.has("rebuild_wires")) {
    return 'Fix the safety notes above, or say "rebuild the wiring" if something looks wrong.';
  }

  if (
    snapshot.wireCount > 0
    && snapshot.safety.errors === 0
    && snapshot.drc.pass
    && !ran.has("generate_firmware")
    && !ran.has("export_bom")
  ) {
    return 'When you\'re ready: "write the code for this board" (downloads a PlatformIO ZIP) or "what do I need to buy?"';
  }

  if (ran.has("generate_firmware") && !ran.has("export_bom")) {
    return 'Upload the code, then ask for "the shopping list" if you still need parts.';
  }

  if (ran.has("check_design") && snapshot.drc.pass && !ran.has("manufacture") && snapshot.moduleCount >= 3) {
    return 'To order PCBs later, say "order boards made" — I\'ll check fab readiness first.';
  }

  return null;
}
