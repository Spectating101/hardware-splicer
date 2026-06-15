#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
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

const {
  generateFirmwareScaffold,
  inferBuildIdFromGraph,
} = require("../lib/firmware/firmware-scaffold.ts");
const { extractPinsFromGraph } = require("../lib/firmware/graph-pin-map.ts");
const { splicePlanToBuildGraph } = require("../lib/salvage/plan-to-graph.ts");
const { expandAndDetectTools } = require("../lib/jarvis/build-tool-planner.ts");

let failed = 0;

const plant = splicePlanToBuildGraph({ target: { recommended_build_id: "automatic_plant_watering" } }).graph;
const buildId = inferBuildIdFromGraph(plant);
if (buildId !== "automatic_plant_watering") {
  failed += 1;
  console.error("FAIL infer plant", buildId);
} else {
  console.log("OK infer plant watering");
}

const pins = extractPinsFromGraph(plant);
if (pins.soil !== 34 || pins.pump !== 4) {
  failed += 1;
  console.error("FAIL plant pin map", pins);
} else {
  console.log("OK plant pin map from graph");
}

const fw = generateFirmwareScaffold(buildId, plant);
if (!fw.source.includes("SOIL_PIN = 34") || !fw.source.includes("PUMP_PIN = 4") || !fw.filename.endsWith(".ino")) {
  failed += 1;
  console.error("FAIL plant firmware body");
} else {
  console.log("OK plant firmware scaffold");
}

const display = splicePlanToBuildGraph({ target: { recommended_build_id: "room_display_station" } }).graph;
const displayFw = generateFirmwareScaffold("room_display_station", display);
if (!displayFw.source.includes("TFT_CS") || !displayFw.source.includes("DHT_PIN")) {
  failed += 1;
  console.error("FAIL room display firmware");
} else {
  console.log("OK room display firmware");
}

const tools = expandAndDetectTools("write the code for this", { moduleCount: 3, wireCount: 5 }).map((t) => t.name);
if (!tools.includes("generate_firmware")) {
  failed += 1;
  console.error("FAIL firmware intent", tools);
} else {
  console.log("OK firmware tool intent");
}

if (failed) process.exit(1);
console.log("OK firmware scaffold");
