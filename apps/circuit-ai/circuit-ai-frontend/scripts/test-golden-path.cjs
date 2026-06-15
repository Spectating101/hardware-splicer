#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * End-to-end golden path: talk → parts → wires → safety → firmware pins → BOM intent.
 */
const path = require("path");
const fs = require("fs");
const Module = require("module");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveAlias(request, parent, isMain, options) {
  if (request.startsWith("@/")) {
    return originalResolve.call(this, path.join(root, request.slice(2)), parent, isMain, options);
  }
  return originalResolve.call(this, request, parent, isMain, options);
};
require.extensions[".ts"] = (mod, filename) => {
  mod._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019, esModuleInterop: true },
  }).outputText, filename);
};

const { expandAndDetectTools } = require("../lib/jarvis/build-tool-planner.ts");
const { splicePlanToBuildGraph } = require("../lib/salvage/plan-to-graph.ts");
const { analyzeBuild } = require("../lib/rules/safety-rules.ts");
const { buildGraphToGeometry } = require("../lib/pcb/build-to-geometry.ts");
const { runDrc } = require("../lib/pcb/drc.ts");
const { buildFirmwareBundle } = require("../lib/firmware/firmware-bundle.ts");
const { inferBuildIdFromGraph } = require("../lib/firmware/firmware-scaffold.ts");
const { runLocalManufacturePreflight } = require("../lib/manufacture/local-preflight.ts");
const { extractPinsFromGraph } = require("../lib/firmware/graph-pin-map.ts");
const { formatBuildToolSummary } = require("../lib/jarvis/build-agent.ts");
const { suggestJarvisNextSteps } = require("../lib/jarvis/next-steps.ts");

let failed = 0;
function fail(msg) {
  failed += 1;
  console.error("FAIL:", msg);
}

// 1. User asks in plain language
const phrase = "water my plants when the soil is dry";
const tools = expandAndDetectTools(phrase, { moduleCount: 0, wireCount: 0 }).map((t) => t.name);
if (!tools.includes("splice_recipe")) {
  fail(`expected splice_recipe, got ${tools.join(",")}`);
}

// 2. Recipe loads with wires
const translated = splicePlanToBuildGraph({ target: { recommended_build_id: "automatic_plant_watering" } });
const graph = translated.graph;
if (graph.nodes.length < 4) fail(`too few nodes: ${graph.nodes.length}`);
if (graph.wires.length < 8) fail(`too few wires: ${graph.wires.length}`);

// 3. Safety + DRC
const safety = analyzeBuild(graph);
if (safety.some((w) => w.level === "error")) {
  fail(`safety errors: ${safety.filter((w) => w.level === "error").map((w) => w.message).join("; ")}`);
}
const drc = runDrc(buildGraphToGeometry(graph));
if (!drc.pass) fail(`DRC failed: ${drc.violations.map((v) => v.message).slice(0, 2).join("; ")}`);

// 4. Firmware pins from graph (not hardcoded coincidence)
const buildId = inferBuildIdFromGraph(graph);
if (buildId !== "automatic_plant_watering") fail(`build id ${buildId}`);
const pins = extractPinsFromGraph(graph);
if (pins.soil !== 34 || pins.pump !== 4) {
  fail(`expected soil=34 pump=4, got soil=${pins.soil} pump=${pins.pump}`);
}
if (!pins.sourcedFromGraph) fail("pins should be sourced from graph");

const bundle = buildFirmwareBundle(buildId, graph);
if (!bundle.files["platformio.ini"] || !bundle.files["src/main.cpp"].includes("SOIL_PIN = 34")) {
  fail("firmware bundle missing graph-derived pins");
}
if (!bundle.files["README.txt"]) fail("bundle missing README");

const localMfg = runLocalManufacturePreflight(graph);
if (!localMfg.kicad_valid) fail("local manufacture kicad invalid");

// 5. Next-step + summary helpers
const mockSnapshot = {
  moduleCount: graph.nodes.length,
  wireCount: graph.wires.length,
  modules: [],
  wires: [],
  safety: { errors: 0, warns: 0, infos: 0, messages: [] },
  drc: { pass: true, errors: 0, warnings: 0, messages: [] },
};
const mockResults = [{
  tool: "splice_recipe",
  ok: true,
  buildId: "automatic_plant_watering",
  moduleCount: graph.nodes.length,
  wireCount: graph.wires.length,
  detail: "ok",
}];
const summary = formatBuildToolSummary(mockResults, mockSnapshot);
if (!summary.includes("Next,")) fail("summary should include next-step prompt");
const next = suggestJarvisNextSteps(mockResults, mockSnapshot);
if (!next || !/safe to plug in/i.test(next)) fail(`unexpected next step: ${next}`);

// 6. Downstream intents
for (const [p, tool] of [
  ["is it safe to plug in", "check_design"],
  ["write the code for this board", "generate_firmware"],
  ["what do I need to buy", "export_bom"],
]) {
  const t = expandAndDetectTools(p, { moduleCount: graph.nodes.length, wireCount: graph.wires.length }).map((x) => x.name);
  if (!t.includes(tool)) fail(`${p} → expected ${tool}, got ${t.join(",")}`);
}

if (failed) process.exit(1);
console.log("OK golden path: plant watering → wired → safe → firmware pins → next steps");
