#!/usr/bin/env node
/**
 * Export salvage module library + catalog build recipes to JSON.
 *
 * Usage:
 *   node scripts/export_module_library.cjs --out examples/module_library.json
 */
const fs = require("fs");
const path = require("path");
const Module = require("module");

const ROOT = path.resolve(__dirname, "..");
const FRONTEND = path.join(ROOT, "apps", "circuit-ai", "circuit-ai-frontend");

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

const { MODULE_LIBRARY } = require(path.join(FRONTEND, "lib/modules/module-library.ts"));
const { SUPPORTED_BUILD_IDS } = require(path.join(FRONTEND, "lib/salvage/plan-to-graph.ts"));

function parseArgs(argv) {
  const args = { out: path.join(ROOT, "examples", "module_library.json") };
  for (let i = 2; i < argv.length; i += 1) {
    if (argv[i] === "--out" && argv[i + 1]) args.out = path.resolve(argv[++i]);
    if (argv[i] === "--help" || argv[i] === "-h") {
      console.log("Usage: node scripts/export_module_library.cjs [--out path]");
      process.exit(0);
    }
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv);
  const payload = {
    schema_version: "hardware_splicer.module_library.v1",
    exported_at: new Date().toISOString(),
    module_count: Object.keys(MODULE_LIBRARY || {}).length,
    build_ids: SUPPORTED_BUILD_IDS,
    modules: MODULE_LIBRARY,
  };
  fs.mkdirSync(path.dirname(args.out), { recursive: true });
  fs.writeFileSync(args.out, JSON.stringify(payload, null, 2));
  console.log(
    JSON.stringify({
      ok: true,
      out: args.out,
      module_count: payload.module_count,
      build_count: payload.build_ids.length,
    }),
  );
}

main();
