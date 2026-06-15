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

const { expandUserPhrase } = require("../lib/jarvis/phrase-expander.ts");
const { expandAndDetectTools } = require("../lib/jarvis/build-tool-planner.ts");

const cases = [
  ["make my plants happy", "splice_recipe"],
  ["is it safe to plug in", "check_design"],
  ["write the code for this board", "generate_firmware"],
  ["get the shopping list", "export_bom"],
  ["order boards made", "manufacture"],
  ["what do I need to buy", "export_bom"],
  ["hook this up for me", "auto_wire"],
  ["I don't know anything about electronics", "check_design"],
  ["am I going to burn my house down", "check_design"],
  ["room temp on a small screen", "splice_recipe"],
];

let failed = 0;
for (const [phrase, ...expectTools] of cases) {
  const expanded = expandUserPhrase(phrase);
  const tools = expandAndDetectTools(phrase, { moduleCount: 0, wireCount: 0 }).map((t) => t.name);
  const ok = expectTools.every((t) => tools.includes(t) || expanded.includes(t));
  if (!ok) {
    failed += 1;
    console.error("FAIL:", phrase, "→", tools, "expanded:", expanded.slice(0, 80));
  } else {
    console.log("OK:", phrase.slice(0, 40));
  }
}

if (failed) process.exit(1);
console.log("OK phrase expander");
