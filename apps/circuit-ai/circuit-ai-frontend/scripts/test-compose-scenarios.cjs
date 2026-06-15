#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * End-to-end compose + wire + DRC scenarios inspired by common CNX Software /
 * maker-blog project patterns (plant care, env sensors, distance, relay, etc.).
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
  const source = fs.readFileSync(filename, "utf8");
  mod._compile(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019, esModuleInterop: true },
  }).outputText, filename);
};

const { pickModulesForGoal } = require("../lib/jarvis/build-module-picker.ts");
const {
  detectBuildToolInvocations,
  inferBuildFromFunction,
} = require("../lib/jarvis/build-agent.ts");
const {
  composeBuildGraphFromModuleIds,
  composeBuildGraphFromCanvasNodes,
  splicePlanToBuildGraph,
} = require("../lib/salvage/plan-to-graph.ts");
const { analyzeBuild } = require("../lib/rules/safety-rules.ts");
const { buildGraphToGeometry } = require("../lib/pcb/build-to-geometry.ts");
const { runDrc } = require("../lib/pcb/drc.ts");

function hasWire(graph, moduleId, pinId) {
  return graph.wires.some(
    (w) => (w.from.pinId === pinId && graph.nodes.find((n) => n.id === w.from.nodeId)?.moduleId === moduleId)
      || (w.to.pinId === pinId && graph.nodes.find((n) => n.id === w.to.nodeId)?.moduleId === moduleId),
  );
}

function mcuGpioToSensor(graph, sensorId, sensorPin) {
  const direct = graph.wires.some((w) => {
    const fromMod = graph.nodes.find((n) => n.id === w.from.nodeId)?.moduleId;
    const toMod = graph.nodes.find((n) => n.id === w.to.nodeId)?.moduleId;
    const involvesSensor = fromMod === sensorId || toMod === sensorId;
    const involvesPin = w.from.pinId === sensorPin || w.to.pinId === sensorPin;
    const involvesMcu = fromMod === "esp32-devkit" || toMod === "esp32-devkit";
    return involvesSensor && involvesPin && involvesMcu;
  });
  if (direct) return true;

  const viaShifter = graph.wires.some((w) => {
    const fromMod = graph.nodes.find((n) => n.id === w.from.nodeId)?.moduleId;
    const toMod = graph.nodes.find((n) => n.id === w.to.nodeId)?.moduleId;
    const toSensor = (fromMod === sensorId && w.from.pinId === sensorPin)
      || (toMod === sensorId && w.to.pinId === sensorPin);
    const shifterPin = ["HV1", "HV2", "LV1", "LV2"].includes(w.from.pinId)
      || ["HV1", "HV2", "LV1", "LV2"].includes(w.to.pinId);
    const shifterInvolved = fromMod === "level-shifter-4ch" || toMod === "level-shifter-4ch";
    return toSensor && shifterInvolved && shifterPin;
  });
  return viaShifter;
}

function verifyCompose(phrase, opts = {}) {
  const pick = pickModulesForGoal(phrase);
  if (pick.moduleIds.length < 2) {
    return { ok: false, reason: `pick too small: ${pick.moduleIds.join(",")}` };
  }
  const composed = composeBuildGraphFromModuleIds(pick.moduleIds);
  const graph = composed.graph;
  if (graph.nodes.length < 2) {
    return { ok: false, reason: "compose returned <2 nodes" };
  }
  if (graph.wires.length < 3) {
    return { ok: false, reason: `only ${graph.wires.length} wires` };
  }

  const safety = analyzeBuild(graph);
  const drc = runDrc(buildGraphToGeometry(graph));
  if (safety.some((w) => w.level === "error")) {
    return { ok: false, reason: `safety errors: ${safety.filter((w) => w.level === "error").map((w) => w.message).join("; ")}` };
  }
  if (!drc.pass) {
    return { ok: false, reason: `DRC fail: ${drc.violations.filter((v) => v.severity === "error").map((v) => v.message).slice(0, 2).join("; ")}` };
  }

  if (opts.signalPin && opts.sensorId) {
    if (!mcuGpioToSensor(graph, opts.sensorId, opts.signalPin)) {
      return { ok: false, reason: `missing MCU→${opts.sensorId}.${opts.signalPin}` };
    }
  }

  return {
    ok: true,
    modules: pick.moduleIds.length,
    wires: graph.wires.length,
    hints: pick.hints,
  };
}

function verifySplice(phrase, buildId, minWires = 4) {
  const inferred = inferBuildFromFunction(phrase);
  if (inferred?.buildId !== buildId) {
    return { ok: false, reason: `inferred ${inferred?.buildId} not ${buildId}` };
  }
  const result = splicePlanToBuildGraph({ target: { recommended_build_id: buildId } });
  const graph = result.graph;
  if (graph.wires.length < minWires) {
    return { ok: false, reason: `only ${graph.wires.length} wires` };
  }
  const drc = runDrc(buildGraphToGeometry(graph));
  if (!drc.pass) {
    return { ok: false, reason: "DRC fail" };
  }
  return { ok: true, modules: graph.nodes.length, wires: graph.wires.length };
}

/** Partial add: ESP32 already on canvas, user asks to add distance sensor. */
function verifyPumpThroughMosfet(phrase) {
  const pick = pickModulesForGoal(phrase);
  const graph = composeBuildGraphFromModuleIds(pick.moduleIds).graph;
  const pumpId = pick.moduleIds.find((id) => /pump|fan/.test(id));
  if (!pumpId) return { ok: false, reason: "no pump/fan in pick" };
  const pumpPoweredFromMos = graph.wires.some((w) => {
    const fromMod = graph.nodes.find((n) => n.id === w.from.nodeId)?.moduleId;
    const toMod = graph.nodes.find((n) => n.id === w.to.nodeId)?.moduleId;
    return (fromMod === "mosfet-irlz44n" && w.from.pinId === "VOUT+" && toMod === pumpId)
      || (toMod === "mosfet-irlz44n" && w.to.pinId === "VOUT+" && fromMod === pumpId);
  });
  if (!pumpPoweredFromMos) return { ok: false, reason: `${pumpId} not fed through MOSFET VOUT+` };
  return { ok: true };
}

function verifyPartialAdd() {
  const phrase = "add an ultrasonic distance sensor";
  const tools = detectBuildToolInvocations(phrase, { moduleCount: 2, wireCount: 4 }).map((t) => t.name);
  if (!tools.includes("compose_modules")) {
    return { ok: false, reason: `expected compose_modules, got ${tools.join(",")}` };
  }
  const base = composeBuildGraphFromCanvasNodes([
    { id: "n1", moduleId: "usb-power-5v" },
    { id: "n2", moduleId: "esp32-devkit" },
  ]);
  const merged = composeBuildGraphFromCanvasNodes([
    { id: "n1", moduleId: "usb-power-5v" },
    { id: "n2", moduleId: "esp32-devkit" },
    { id: "n3", moduleId: "hc-sr04" },
  ]);
  if (!mcuGpioToSensor(merged, "hc-sr04", "TRIG")) {
    return { ok: false, reason: "hc-sr04 TRIG not wired" };
  }
  if (merged.wires.length <= base.wires.length) {
    return { ok: false, reason: "no new wires after adding sensor" };
  }
  return { ok: true, wires: merged.wires.length };
}

const composeCases = [
  ["something that measures temperature", { sensorId: "dht22", signalPin: "DATA" }],
  ["need something that senses distance", { sensorId: "hc-sr04", signalPin: "TRIG" }],
  ["read air quality in the kitchen", { sensorId: "mq-2_gas_sensor", signalPin: "A0" }],
  ["a one wire temperature probe", { sensorId: "ds18b20", signalPin: "DATA" }],
  ["environmental sensor for pressure and humidity", { sensorId: "bme280", signalPin: "SDA" }],
  ["control a 5v pump for drip irrigation", { sensorId: "mosfet-irlz44n", signalPin: "SIG" }],
  ["desk fan to blow air across my project", { sensorId: "mosfet-irlz44n", signalPin: "SIG" }],
  ["switch a lamp with a relay", { sensorId: "relay-1ch-5v", signalPin: "IN" }],
  ["room monitor with a small screen", { sensorId: "bme280", signalPin: "SDA" }],
];

const spliceCases = [
  ["$12 plant bot for indoor plant care when soil is dry", "automatic_plant_watering"],
  ["help me track temperature and humidity in my room", "sensor_logger"],
  ["desk fan so solder smoke doesn't stink", "usb_fume_extractor"],
  ["little robot that drives around", "robot_drive_base"],
  ["wifi analyzer on a small display", "network_status_indicator"],
];

let failed = 0;

for (const [phrase, opts] of composeCases) {
  const r = verifyCompose(phrase, opts);
  if (!r.ok) {
    failed += 1;
    console.error("FAIL compose:", phrase);
    console.error(" ", r.reason);
  } else {
    console.log(`OK compose: ${phrase.slice(0, 48)} → ${r.modules} mods, ${r.wires} wires`);
  }
}

for (const [phrase, buildId] of spliceCases) {
  const r = verifySplice(phrase, buildId);
  if (!r.ok) {
    failed += 1;
    console.error("FAIL splice:", phrase);
    console.error(" ", r.reason);
  } else {
    console.log(`OK splice: ${phrase.slice(0, 48)} → ${r.modules} mods, ${r.wires} wires`);
  }
}

const partial = verifyPartialAdd();
if (!partial.ok) {
  failed += 1;
  console.error("FAIL partial add:", partial.reason);
} else {
  console.log(`OK partial add: distance sensor → ${partial.wires} wires`);
}

const pumpChain = verifyPumpThroughMosfet("control a 5v pump for drip irrigation");
if (!pumpChain.ok) {
  failed += 1;
  console.error("FAIL pump chain:", pumpChain.reason);
} else {
  console.log("OK pump fed through MOSFET switch");
}

const envPick = pickModulesForGoal("environmental sensor for pressure and humidity");
if (envPick.moduleIds.includes("joystick_module") || (envPick.moduleIds.includes("dht22") && envPick.moduleIds.includes("bme280"))) {
  failed += 1;
  console.error("FAIL env pick should prefer bme280 only", envPick.moduleIds);
} else if (!envPick.moduleIds.includes("bme280")) {
  failed += 1;
  console.error("FAIL env pick missing bme280", envPick.moduleIds);
} else {
  console.log("OK env sensor dedup → bme280");
}

if (failed) process.exit(1);
console.log(`OK all ${composeCases.length + spliceCases.length + 3} CNX-style scenarios`);
