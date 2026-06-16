#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Export CATALOG_RECIPES + BUILD_CATALOG_CAPABILITY_GROUPS to Python engine data.
 * Run after editing plan-to-graph.ts recipes; commit the JSON output.
 */
const fs = require("fs");
const path = require("path");
const Module = require("module");

const ROOT = path.resolve(__dirname, "..");
const FRONTEND = path.join(ROOT, "apps/circuit-ai/circuit-ai-frontend");
const OUT = path.join(ROOT, "src/hardware_splicer/data/catalog_recipes.json");

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveAlias(request, parent, isMain, options) {
  if (request.startsWith("@/")) {
    return originalResolve.call(this, path.join(FRONTEND, request.slice(2)), parent, isMain, options);
  }
  return originalResolve.call(this, request, parent, isMain, options);
};

const TS_LIB = path.join(FRONTEND, "node_modules", "typescript", "lib", "typescript.js");
const ts = fs.existsSync(TS_LIB) ? require(TS_LIB) : require("typescript");

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
  CATALOG_RECIPES,
  BUILD_CATALOG_CAPABILITY_GROUPS,
  SUPPORTED_BUILD_IDS,
} = require(path.join(FRONTEND, "lib/salvage/plan-to-graph.ts"));

const payload = {
  schema_version: "hardware_splicer.catalog_recipes.v1",
  supported_build_ids: SUPPORTED_BUILD_IDS,
  build_catalog_capability_groups: BUILD_CATALOG_CAPABILITY_GROUPS,
  recipes: CATALOG_RECIPES,
};

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(`Wrote ${OUT} (${SUPPORTED_BUILD_IDS.length} recipes)`);
