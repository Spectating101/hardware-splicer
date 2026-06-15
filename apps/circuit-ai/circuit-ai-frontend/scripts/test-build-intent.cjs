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
  const source = fs.readFileSync(filename, "utf8");
  mod._compile(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019, esModuleInterop: true },
  }).outputText, filename);
};

const {
  inferBuildFromFunction,
  detectBuildToolInvocations,
} = require("../lib/jarvis/build-agent.ts");
const { expandAndDetectTools } = require("../lib/jarvis/build-tool-planner.ts");
const { pickModulesForGoal } = require("../lib/jarvis/build-module-picker.ts");

const cases = [
  ["I need something to water my plants when the soil dries out", "automatic_plant_watering", ["splice_recipe"]],
  ["help me track temperature and humidity in my room", "sensor_logger", ["splice_recipe"]],
  ["little robot that drives around", "robot_drive_base", ["splice_recipe"]],
  ["desk fan so solder smoke doesn't stink", "usb_fume_extractor", ["splice_recipe"]],
  ["something that measures temperature", null, ["compose_modules"]],
  ["I want a relay to switch a lamp", "smart_relay_box", ["splice_recipe"]],
  ["need something that senses distance", null, ["compose_modules"]],
  ["make it work", null, ["auto_wire"]],
  ["will this blow up if I plug it in", null, ["check_design"]],
  ["show me the circuit board", null, ["open_pcb"]],
  ["indoor plant care with a moisture sensor", "automatic_plant_watering", ["splice_recipe"]],
  ["add an ultrasonic distance sensor", null, ["compose_modules"]],
  ["wifi analyzer on a small display", "network_status_indicator", ["splice_recipe"]],
  ["add a temp sensor to my robot", null, ["compose_modules"]],
  ["hook up what I have on the board", null, ["auto_wire"]],
  ["make my plants happy", "automatic_plant_watering", ["splice_recipe"]],
  ["is it safe to plug in", null, ["check_design"]],
  ["write the code for this board", null, ["generate_firmware"]],
  ["what do I need to buy", null, ["export_bom"]],
  ["hook this up for me", null, ["auto_wire"]],
  ["where do I start", "automatic_plant_watering", ["splice_recipe"]],
  ["I don't know anything about electronics but want room temperature", null, ["compose_modules"]],
  ["am I going to burn my house down", null, ["check_design"]],
];

let failed = 0;
for (const [text, expectedBuild, expectedTools] of cases) {
  const inferred = inferBuildFromFunction(text);
  const tools = detectBuildToolInvocations(text, { moduleCount: 0, wireCount: 0 }).map((t) => t.name);
  const buildOk = expectedBuild ? inferred?.buildId === expectedBuild : true;
  const toolsOk = expectedTools.every((t) => tools.includes(t));
  if (!buildOk || !toolsOk) {
    failed += 1;
    console.error("FAIL:", text);
    console.error("  inferred:", inferred?.buildId, "expected:", expectedBuild);
    console.error("  tools:", tools, "expected includes:", expectedTools);
  } else {
    console.log("OK:", text.slice(0, 50));
  }
}

const tempPick = pickModulesForGoal("something that measures temperature");
if (!tempPick.moduleIds.includes("dht22")) {
  failed += 1;
  console.error("FAIL: temperature pick should include dht22", tempPick.moduleIds);
} else {
  console.log("OK: temperature module pick");
}
const addTools = detectBuildToolInvocations("add a distance sensor to my board", { moduleCount: 2, wireCount: 3 }).map((t) => t.name);
if (!addTools.includes("compose_modules")) {
  failed += 1;
  console.error("FAIL: partial-add should trigger compose_modules", addTools);
} else {
  console.log("OK: partial-add compose intent");
}

const noSpliceOnAdd = detectBuildToolInvocations("add a relay to switch a lamp", { moduleCount: 3, wireCount: 5 }).map((t) => t.name);
if (noSpliceOnAdd.includes("splice_recipe")) {
  failed += 1;
  console.error("FAIL: add-to-canvas should not splice over existing board", noSpliceOnAdd);
} else if (!noSpliceOnAdd.includes("compose_modules")) {
  failed += 1;
  console.error("FAIL: add relay should compose", noSpliceOnAdd);
} else {
  console.log("OK: add-to-canvas avoids catalog splice");
}

const rewireOnly = detectBuildToolInvocations("make it work", { moduleCount: 3, wireCount: 0 }).map((t) => t.name);
if (!rewireOnly.includes("auto_wire")) {
  failed += 1;
  console.error("FAIL: unwired canvas should auto_wire", rewireOnly);
} else {
  console.log("OK: unwired canvas auto_wire");
}

if (failed) process.exit(1);
console.log("OK all build intent cases");
