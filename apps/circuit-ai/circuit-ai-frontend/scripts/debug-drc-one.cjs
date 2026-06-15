#!/usr/bin/env node
const path = require("path");
const Module = require("module");
const ts = require("typescript");
const fs = require("fs");
const root = path.resolve(__dirname, "..");
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, isMain, options) {
  if (request.startsWith("@/")) {
    return originalResolve.call(this, path.join(root, request.slice(2)), parent, isMain, options);
  }
  return originalResolve.call(this, request, parent, isMain, options);
};
require.extensions[".ts"] = (mod, filename) => {
  const source = fs.readFileSync(filename, "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019, esModuleInterop: true },
  }).outputText;
  mod._compile(output, filename);
};
const { splicePlanToBuildGraph } = require("../lib/salvage/plan-to-graph.ts");
const { buildGraphToGeometry } = require("../lib/pcb/build-to-geometry.ts");
const { runDrc } = require("../lib/pcb/drc.ts");

const buildId = process.argv[2] || "usb_fume_extractor";
const translated = splicePlanToBuildGraph({
  target: { recommended_build_id: buildId },
  reusable_blocks: [{ id: "fixture", name: "validation fixture", capabilities: ["test"] }],
});
const geo = buildGraphToGeometry(translated.graph);
const drc = runDrc(geo);
console.log("build:", buildId);
console.log("modules:", translated.graph.nodes.map((n) => n.moduleId).join(", "));
for (const fp of geo.footprints) {
  console.log(fp.ref, fp.value, fp.pads.map((p) => `${p.num}:${p.net.name}@(${p.wx.toFixed(1)},${p.wy.toFixed(1)})`).join(" "));
}
console.log("DRC pass:", drc.pass, "errors:", drc.summary.errors);
for (const v of drc.violations.slice(0, 12)) console.log("-", v.message);
