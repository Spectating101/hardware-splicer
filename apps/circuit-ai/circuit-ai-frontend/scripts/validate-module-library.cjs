#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */

const fs = require("fs");
const path = require("path");
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
  const source = fs.readFileSync(filename, "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2019,
      jsx: ts.JsxEmit.React,
      esModuleInterop: true,
    },
  }).outputText;
  mod._compile(output, filename);
};

const {
  MODULE_LIBRARY,
  findModule,
  findPin,
  findModulesByCapabilities,
  searchModules,
} = require("../lib/modules/module-library.ts");
const {
  SUPPORTED_BUILD_IDS,
  splicePlanToBuildGraph,
} = require("../lib/salvage/plan-to-graph.ts");
const { analyzeBuild } = require("../lib/rules/safety-rules.ts");
const { buildGraphToGeometry } = require("../lib/pcb/build-to-geometry.ts");
const { runDrc } = require("../lib/pcb/drc.ts");
const { serializeBuildToKicadPcb } = require("../lib/kicad-serializer.ts");

const errors = [];
const warnings = [];

function fail(message) {
  errors.push(message);
}

function warn(message) {
  warnings.push(message);
}

function countBy(items, keyOf) {
  const counts = {};
  for (const item of items) {
    const key = keyOf(item);
    counts[key] = (counts[key] || 0) + 1;
  }
  return counts;
}

function requireIds(label, ids) {
  for (const id of ids) {
    if (!findModule(id)) fail(`${label}: missing module ${id}`);
  }
}

const MIN_MODULES = 154;
const MIN_SOURCE_COUNTS = {
  "curated-original": 21,
  curated: 23,
  "ingested-kb-board": 4,
  "ingested-kb-ic": 2,
  "ingested-datasheet-pdf": 5,
  "ingested-component-db": 87,
  "ingested-pinout-extract": 12,
};
const REQUIRED_WAVE2_IDS = [
  "max98357a-i2s-amp",
  "bno055-imu",
  "mcp23017-ioexp",
  "vl6180x-tof",
  "tb6612fng-motor",
  "lc709203f-fuel-gauge",
  "qtpy-esp32s3",
  "max30102-pulse-ox",
  "tmc2209-stepper",
  "scd41-co2",
];
const REQUIRED_BUILD_IDS = [
  "bench_power_adapter",
  "camera_ir_light_or_sensor_mount",
  "indicator_or_task_light",
  "inspection_motion_fixture",
  "low_voltage_motor_test_jig",
  "network_status_indicator",
  "plotter_motion_stage",
  "robot_drive_base",
  "salvaged_input_panel",
  "sensor_logger",
  "small_audio_amp_box",
  "smart_relay_box",
  "usb_fume_extractor",
  "usb_uart_debug_adapter",
];

if (MODULE_LIBRARY.length < MIN_MODULES) {
  fail(`module count regressed: expected at least ${MIN_MODULES}, got ${MODULE_LIBRARY.length}`);
}

const seen = new Set();
for (const moduleSpec of MODULE_LIBRARY) {
  if (!moduleSpec.id) fail("module without id");
  if (seen.has(moduleSpec.id)) fail(`duplicate module id: ${moduleSpec.id}`);
  seen.add(moduleSpec.id);

  if (!moduleSpec.label) fail(`${moduleSpec.id}: missing label`);
  if (!moduleSpec.summary) fail(`${moduleSpec.id}: missing summary`);
  if (!moduleSpec.category) fail(`${moduleSpec.id}: missing category`);
  if (!Array.isArray(moduleSpec.pins) || moduleSpec.pins.length === 0) {
    fail(`${moduleSpec.id}: missing pinout`);
    continue;
  }

  const pins = new Set();
  for (const pin of moduleSpec.pins) {
    if (!pin.id) fail(`${moduleSpec.id}: pin without id`);
    if (pins.has(pin.id)) fail(`${moduleSpec.id}: duplicate pin ${pin.id}`);
    pins.add(pin.id);
    if (!pin.label) fail(`${moduleSpec.id}.${pin.id}: missing label`);
    if (!pin.role) fail(`${moduleSpec.id}.${pin.id}: missing role`);
  }

  if (!Array.isArray(moduleSpec.capabilityTags) || moduleSpec.capabilityTags.length === 0) {
    fail(`${moduleSpec.id}: missing capabilityTags`);
  }
}

const sourceCounts = countBy(MODULE_LIBRARY, (m) => m.source || "curated-original");
for (const [source, min] of Object.entries(MIN_SOURCE_COUNTS)) {
  const actual = sourceCounts[source] || 0;
  if (actual < min) fail(`${source}: expected at least ${min}, got ${actual}`);
}

requireIds("wave-2 curated library", REQUIRED_WAVE2_IDS);
for (const id of REQUIRED_WAVE2_IDS) {
  const moduleSpec = findModule(id);
  if (!moduleSpec) continue;
  if (!moduleSpec.datasheetUrl) fail(`${id}: missing datasheetUrl`);
  if (!moduleSpec.capabilityTags || moduleSpec.capabilityTags.length === 0) {
    fail(`${id}: missing capabilityTags`);
  }
}

const searchCases = [
  ["MCP23017", "mcp23017-ioexp"],
  ["Bosch", "bno055-imu"],
  ["SCD41", "scd41-co2"],
  ["TB6612FNG", "tb6612fng-motor"],
];
for (const [query, expectedId] of searchCases) {
  const hits = searchModules(query).map((m) => m.id);
  if (!hits.includes(expectedId)) {
    fail(`searchModules(${JSON.stringify(query)}) did not include ${expectedId}`);
  }
}

const capabilityCases = [
  [["speaker_or_audio"], "max98357a-i2s-amp"],
  [["actuator_driver"], ["motor_or_load"], "tb6612fng-motor"],
  [["power"], ["battery"], "lc709203f-fuel-gauge"],
  [["connector"], ["switch_or_button"], "mcp23017-ioexp"],
];
for (const entry of capabilityCases) {
  const expectedId = entry[entry.length - 1];
  const requiresAny = entry.slice(0, -1);
  const hits = findModulesByCapabilities(requiresAny).map((m) => m.id);
  if (!hits.includes(expectedId)) {
    fail(`capability lookup ${JSON.stringify(requiresAny)} did not include ${expectedId}`);
  }
}

for (const id of REQUIRED_BUILD_IDS) {
  if (!SUPPORTED_BUILD_IDS.includes(id)) fail(`translator missing supported build id ${id}`);
}

let translatorElectricalWarnings = 0;
let translatorDrcWarnings = 0;
for (const buildId of REQUIRED_BUILD_IDS) {
  const translated = splicePlanToBuildGraph({
    target: { recommended_build_id: buildId },
    reusable_blocks: [{ id: "fixture", name: "validation fixture", capabilities: ["test"] }],
  });

  if (translated.buildId !== buildId) fail(`${buildId}: translated buildId mismatch`);
  if (translated.warnings.length > 0) fail(`${buildId}: translator warnings: ${translated.warnings.join("; ")}`);
  if (translated.graph.nodes.length === 0) fail(`${buildId}: no graph nodes`);
  if (translated.graph.wires.length === 0) fail(`${buildId}: no graph wires`);

  for (const node of translated.graph.nodes) {
    if (!findModule(node.moduleId)) fail(`${buildId}: unknown module ${node.moduleId}`);
  }
  for (const wire of translated.graph.wires) {
    const fromNode = translated.graph.nodes.find((n) => n.id === wire.from.nodeId);
    const toNode = translated.graph.nodes.find((n) => n.id === wire.to.nodeId);
    const fromModule = fromNode && findModule(fromNode.moduleId);
    const toModule = toNode && findModule(toNode.moduleId);
    if (!fromModule) fail(`${buildId}: wire ${wire.id} unknown from node ${wire.from.nodeId}`);
    if (!toModule) fail(`${buildId}: wire ${wire.id} unknown to node ${wire.to.nodeId}`);
    if (fromModule && !findPin(fromModule, wire.from.pinId)) {
      fail(`${buildId}: wire ${wire.id} unknown from pin ${fromModule.id}.${wire.from.pinId}`);
    }
    if (toModule && !findPin(toModule, wire.to.pinId)) {
      fail(`${buildId}: wire ${wire.id} unknown to pin ${toModule.id}.${wire.to.pinId}`);
    }
  }

  const electrical = analyzeBuild(translated.graph);
  const electricalErrors = electrical.filter((item) => item.level === "error");
  if (electricalErrors.length > 0) {
    fail(`${buildId}: electrical errors: ${electricalErrors.map((item) => item.message).join("; ")}`);
  }
  translatorElectricalWarnings += electrical.filter((item) => item.level !== "error").length;

  const geometry = buildGraphToGeometry(translated.graph);
  const drc = runDrc(geometry);
  if (drc.summary.errors > 0) {
    fail(`${buildId}: geometry DRC errors: ${drc.violations.map((item) => item.message).join("; ")}`);
  }
  translatorDrcWarnings += drc.summary.warnings;

  const kicad = serializeBuildToKicadPcb(translated.graph);
  if (!kicad.includes("(kicad_pcb") || !kicad.includes("(footprint")) {
    fail(`${buildId}: KiCad serialization did not produce a board with footprints`);
  }
}

if (translatorElectricalWarnings > 0) {
  warn(`${translatorElectricalWarnings} electrical info/warn findings remain across strict recipes`);
}
if (translatorDrcWarnings > 0) {
  warn(`${translatorDrcWarnings} geometry DRC warnings remain across strict recipes`);
}

if (warnings.length > 0) {
  for (const message of warnings) console.warn(`WARN ${message}`);
}

if (errors.length > 0) {
  for (const message of errors) console.error(`FAIL ${message}`);
  process.exit(1);
}

console.log(`OK module library: ${MODULE_LIBRARY.length} modules, ${SUPPORTED_BUILD_IDS.length} salvage translators`);
console.log(`OK source counts: ${JSON.stringify(sourceCounts)}`);
console.log("OK capability search, strict translator wiring, electrical safety, DRC, KiCad serialization");
