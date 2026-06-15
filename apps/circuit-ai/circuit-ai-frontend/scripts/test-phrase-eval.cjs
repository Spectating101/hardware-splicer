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
  inferBuildFromFunction,
  detectBuildToolInvocations,
} = require("../lib/jarvis/build-agent.ts");
const { expandAndDetectTools } = require("../lib/jarvis/build-tool-planner.ts");

const corpusPath = path.join(__dirname, "phrases-eval.json");
const corpus = JSON.parse(fs.readFileSync(corpusPath, "utf8"));
const cases = corpus.cases ?? [];

let failed = 0;
let passed = 0;

for (const c of cases) {
  const ctx = c.ctx ?? { moduleCount: 0, wireCount: 0 };
  const tools = expandAndDetectTools(c.phrase, ctx).map((t) => t.name);
  const inferred = inferBuildFromFunction(c.phrase);

  let ok = true;
  if (c.expectTools) {
    for (const t of c.expectTools) {
      if (!tools.includes(t)) ok = false;
    }
  }
  if (c.expectBuild && inferred?.buildId !== c.expectBuild) ok = false;
  if (c.forbidTools) {
    for (const t of c.forbidTools) {
      if (tools.includes(t)) ok = false;
    }
  }

  if (!ok) {
    failed += 1;
    console.error("FAIL:", c.phrase.slice(0, 60));
    console.error("  tools:", tools, "expected:", c.expectTools);
    console.error("  build:", inferred?.buildId, "expected:", c.expectBuild);
  } else {
    passed += 1;
  }
}

if (cases.length < 80) {
  failed += 1;
  console.error(`FAIL: corpus too small (${cases.length} cases, need >= 80)`);
}

if (failed) process.exit(1);
console.log(`OK phrase eval corpus: ${passed}/${cases.length} cases`);
