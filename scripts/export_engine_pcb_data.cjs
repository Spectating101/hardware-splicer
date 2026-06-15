#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/** Export module library + footprint metadata for the Python PCB engine. */
const fs = require("fs");
const path = require("path");
const Module = require("module");

const ROOT = path.resolve(__dirname, "..");
const FRONTEND = path.join(ROOT, "apps/circuit-ai/circuit-ai-frontend");
const OUT_DIR = path.join(ROOT, "src/hardware_splicer/data");

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
  resolveModulePads,
} = require(path.join(FRONTEND, "lib/modules/module-footprints.ts"));

const footprints = {};
for (const [id, meta] of Object.entries(MODULE_FOOTPRINTS)) {
  const spec = MODULE_LIBRARY.find((m) => m.id === id);
  footprints[id] = {
    kicadFootprint: meta.kicadFootprint,
    bodyMm: meta.bodyMm,
    pads: meta.pads ?? resolveModulePads(id, spec) ?? [],
  };
}

const payload = {
  schema_version: "hardware_splicer.engine_pcb_data.v1",
  module_library: MODULE_LIBRARY,
  module_footprints: footprints,
};

fs.mkdirSync(OUT_DIR, { recursive: true });
const outPath = path.join(OUT_DIR, "engine_pcb_data.json");
fs.writeFileSync(outPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(`Wrote ${outPath} (${MODULE_LIBRARY.length} modules, ${Object.keys(footprints).length} footprints)`);
