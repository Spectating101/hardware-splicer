#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Print, as JSON, what the TypeScript module library resolves for every module: footprint name,
 * body envelope, fit record and pads (including the synthetic fallback for a module with no
 * registered footprint). tests/test_module_footprint_parity.py compares this with the Python
 * registry so the two engines cannot drift.
 */
const fs = require("fs");
const path = require("path");
const Module = require("module");

const ROOT = path.resolve(__dirname, "..");
const FRONTEND = path.join(ROOT, "apps/circuit-ai/circuit-ai-frontend");

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
  mod._compile(
    ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2019,
        jsx: ts.JsxEmit.React,
        esModuleInterop: true,
      },
    }).outputText,
    filename,
  );
};

const { MODULE_LIBRARY } = require(path.join(FRONTEND, "lib/modules/module-library.ts"));
const {
  MODULE_FOOTPRINTS,
  resolveModuleBodyMm,
  resolveModuleFit,
  resolveModuleFootprint,
  resolveModulePads,
} = require(path.join(FRONTEND, "lib/modules/module-footprints.ts"));

const ids = new Set([...MODULE_LIBRARY.map((m) => m.id), ...Object.keys(MODULE_FOOTPRINTS)]);
const out = {};
for (const id of [...ids].sort()) {
  const spec = MODULE_LIBRARY.find((m) => m.id === id);
  out[id] = {
    kicadFootprint: resolveModuleFootprint(id),
    bodyMm: resolveModuleBodyMm(id),
    fit: resolveModuleFit(id),
    pads: resolveModulePads(id, spec),
  };
}
process.stdout.write(`${JSON.stringify(out)}\n`);
