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

const { runLocalManufacturePreflight } = require("../lib/manufacture/local-preflight.ts");
const { formatLocalManufactureSummary } = require("../lib/jarvis/manufacture-summary.ts");
const { splicePlanToBuildGraph } = require("../lib/salvage/plan-to-graph.ts");

let failed = 0;

const plant = splicePlanToBuildGraph({ target: { recommended_build_id: "automatic_plant_watering_usb" } }).graph;
const local = runLocalManufacturePreflight(plant);
if (!local.kicad_valid) {
  failed += 1;
  console.error("FAIL kicad export");
} else if (local.source !== "local") {
  failed += 1;
  console.error("FAIL source tag");
} else {
  console.log("OK local preflight plant usb");
}

const summary = formatLocalManufactureSummary(local);
if (!summary.detail || summary.source !== "local") {
  failed += 1;
  console.error("FAIL local summary");
} else {
  console.log("OK local manufacture summary");
}

const empty = runLocalManufacturePreflight({ nodes: [], wires: [] });
if (empty.manufacturing_ready) {
  failed += 1;
  console.error("FAIL empty should not be ready");
} else {
  console.log("OK empty board blocked");
}

if (failed) process.exit(1);
console.log("OK local manufacture");
