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

const { buildFirmwareBundle } = require("../lib/firmware/firmware-bundle.ts");
const { buildZipStore } = require("../lib/firmware/zip-store.ts");
const { splicePlanToBuildGraph } = require("../lib/salvage/plan-to-graph.ts");

let failed = 0;

const plant = splicePlanToBuildGraph({ target: { recommended_build_id: "automatic_plant_watering" } }).graph;
const plantBundle = buildFirmwareBundle("automatic_plant_watering", plant);
if (!plantBundle.files["platformio.ini"] || !plantBundle.files["src/main.cpp"]) {
  failed += 1;
  console.error("FAIL plant bundle missing files");
} else if (!plantBundle.files["src/main.cpp"].includes("SOIL_PIN = 34")) {
  failed += 1;
  console.error("FAIL plant bundle pins");
} else {
  console.log("OK plant PlatformIO bundle");
}

const display = splicePlanToBuildGraph({ target: { recommended_build_id: "room_display_station" } }).graph;
const displayBundle = buildFirmwareBundle("room_display_station", display);
if (!displayBundle.files["include/tft_user_setup.h"]) {
  failed += 1;
  console.error("FAIL display tft setup missing");
} else if (!displayBundle.files["src/main.cpp"].includes("TFT_eSPI")) {
  failed += 1;
  console.error("FAIL display sketch missing TFT_eSPI");
} else if (!displayBundle.files["include/tft_user_setup.h"].includes("TFT_CS")) {
  failed += 1;
  console.error("FAIL tft pin defines");
} else {
  console.log("OK display TFT bundle");
}

const zip = buildZipStore(plantBundle.files);
if (!(zip instanceof Blob) || zip.size < 200) {
  failed += 1;
  console.error("FAIL zip blob");
} else {
  console.log("OK zip store");
}

if (failed) process.exit(1);
console.log("OK firmware bundle");
