#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */

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
  const source = require("fs").readFileSync(filename, "utf8");
  mod._compile(
    ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2019,
        esModuleInterop: true,
      },
    }).outputText,
    filename,
  );
};

const { splicePlanToBuildGraph } = require("../lib/salvage/plan-to-graph.ts");

const USB_PLAN = {
  power_topology: "usb_5v",
  module_overrides: { pwr: "usb-power-5v" },
};

const cases = [
  {
    buildId: "usb_fume_extractor",
    expectModules: ["usb-power-5v", "mosfet-irlz44n"],
    rejectModules: ["dc-barrel-12v", "buck-mp1584"],
    minNodes: 2,
  },
  {
    buildId: "indicator_or_task_light",
    expectModules: ["usb-power-5v", "mosfet-irlz44n"],
    rejectModules: ["dc-barrel-12v", "buck-mp1584"],
    minNodes: 2,
  },
  {
    buildId: "robot_drive_base",
    expectModules: ["usb-power-5v", "arduino-nano", "l298n"],
    rejectModules: ["dc-barrel-12v", "buck-mp1584"],
    minNodes: 3,
    maxNodes: 3,
  },
  {
    buildId: "inspection_motion_fixture",
    expectModules: ["usb-power-5v", "rpi-pico", "ssd1306-128x64", "sg90"],
    rejectModules: ["dc-barrel-12v", "ldo-ams1117-5v"],
    minNodes: 4,
  },
  {
    buildId: "plotter_motion_stage",
    expectModules: [
      "usb-power-5v",
      "arduino-nano",
      "a4988-stepper",
      "limit-switch-3pin",
      "sg90",
      "ldo-ams1117-5v",
    ],
    rejectModules: ["dc-barrel-12v", "buck-mp1584"],
    minNodes: 6,
  },
  {
    buildId: "low_voltage_motor_test_jig",
    expectModules: ["usb-power-5v", "mosfet-irlz44n"],
    rejectModules: ["dc-barrel-12v", "buck-mp1584"],
    minNodes: 2,
  },
  {
    buildId: "small_audio_amp_box",
    expectModules: ["usb-power-5v", "esp32-devkit", "max98357a-i2s-amp"],
    rejectModules: ["dc-barrel-12v", "buck-mp1584", "mosfet-irlz44n"],
    minNodes: 3,
  },
  {
    buildId: "automatic_plant_watering",
    expectModules: ["usb-power-5v", "esp32-devkit", "soil_moisture", "mosfet-irlz44n"],
    rejectModules: ["dc-barrel-12v", "buck-mp1584"],
    minNodes: 4,
  },
];

let failed = 0;
for (const c of cases) {
  const plan = {
    target: { recommended_build_id: c.buildId },
    ...USB_PLAN,
  };
  const { graph, notes, warnings } = splicePlanToBuildGraph(plan);
  const ids = graph.nodes.map((n) => n.moduleId);
  const problems = [];
  if (graph.nodes.length < c.minNodes) {
    problems.push(`expected >=${c.minNodes} nodes, got ${graph.nodes.length}`);
  }
  if (c.maxNodes != null && graph.nodes.length > c.maxNodes) {
    problems.push(`expected <=${c.maxNodes} nodes, got ${graph.nodes.length}`);
  }
  for (const id of c.expectModules || []) {
    if (!ids.includes(id)) problems.push(`missing module ${id}`);
  }
  for (const id of c.rejectModules || []) {
    if (ids.includes(id)) problems.push(`unexpected module ${id}`);
  }
  if (warnings.length) problems.push(`warnings: ${warnings.join("; ")}`);
  if (problems.length) {
    failed += 1;
    console.error(`FAIL ${c.buildId}: ${problems.join(" | ")}`);
    console.error(`  modules: ${ids.join(", ")}`);
    console.error(`  notes: ${notes.slice(-3).join(" | ")}`);
  } else {
    console.log(`OK ${c.buildId}: ${ids.length} modules (${ids.join(", ")})`);
  }
}

if (failed) process.exit(1);
console.log(`OK inventory topology: ${cases.length} USB transforms`);
