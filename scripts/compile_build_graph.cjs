#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Legacy full compiler: splice plan OR build_graph -> KiCad PCB.
 * Engine path uses Python plan_to_graph + scripts/compile_geometry.cjs.
 */
const fs = require("fs");
const path = require("path");
const Module = require("module");

const ROOT = path.resolve(__dirname, "..");
const FRONTEND = path.join(ROOT, "apps/circuit-ai/circuit-ai-frontend");
const { compileGraph, compileFromGraphFile } = require("./compile_geometry.cjs");

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

const { splicePlanToBuildGraph, SUPPORTED_BUILD_IDS } = require(path.join(
  FRONTEND,
  "lib/salvage/plan-to-graph.ts",
));

function parseArgs(argv) {
  const out = {
    buildId: null,
    outDir: null,
    splicePlanPath: null,
    buildGraphPath: null,
    buildGraphMetaPath: null,
    json: false,
    listBuildIds: false,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--list-build-ids") out.listBuildIds = true;
    else if (arg === "--json") out.json = true;
    else if (arg === "--build-id" && argv[i + 1]) out.buildId = argv[++i];
    else if (arg === "--out" && argv[i + 1]) out.outDir = argv[++i];
    else if (arg === "--splice-plan" && argv[i + 1]) out.splicePlanPath = argv[++i];
    else if (arg === "--build-graph" && argv[i + 1]) out.buildGraphPath = argv[++i];
    else if (arg === "--build-graph-meta" && argv[i + 1]) out.buildGraphMetaPath = argv[++i];
  }
  return out;
}

function loadSplicePlan(planPath, buildId) {
  if (!planPath) return { target: { recommended_build_id: buildId } };
  const raw = JSON.parse(fs.readFileSync(planPath, "utf8"));
  if (raw.graph_input) return raw.graph_input;
  if (raw.target || raw.module_overrides || raw.resolved_modules) return raw;
  if (raw.splice_plan) {
    const body = { ...raw.splice_plan };
    if (raw.module_overrides) body.module_overrides = raw.module_overrides;
    if (raw.resolved_modules) body.resolved_modules = raw.resolved_modules;
    return body;
  }
  return { target: { recommended_build_id: buildId } };
}

function compileBuild(buildId, outDir, splicePlanPath) {
  const plan = loadSplicePlan(splicePlanPath, buildId);
  const effectiveBuildId = plan?.target?.recommended_build_id || buildId;
  if (!plan.target) plan.target = { recommended_build_id: effectiveBuildId };
  const translation = splicePlanToBuildGraph(plan);
  const { graph, notes, warnings } = translation;
  return compileGraph(buildId, outDir, graph, notes, warnings, effectiveBuildId);
}

function main() {
  const args = parseArgs(process.argv);
  if (args.listBuildIds) {
    console.log(JSON.stringify(SUPPORTED_BUILD_IDS));
    process.exit(0);
  }
  if (!args.outDir || (!args.buildGraphPath && !args.buildId)) {
    console.error(
      "Usage: node scripts/compile_build_graph.cjs --build-id <id> --out <dir> [--json] [--splice-plan <path>]\n" +
        "       node scripts/compile_build_graph.cjs --build-id <id> --out <dir> --build-graph <path> [--build-graph-meta <path>]\n" +
        "       node scripts/compile_build_graph.cjs --list-build-ids",
    );
    process.exit(2);
  }
  try {
    const outDir = path.resolve(args.outDir);
    const result = args.buildGraphPath
      ? compileFromGraphFile(args.buildId, outDir, path.resolve(args.buildGraphPath), args.buildGraphMetaPath)
      : compileBuild(args.buildId, outDir, args.splicePlanPath);
    if (args.json) {
      console.log(JSON.stringify(result, null, 2));
    } else {
      console.log(`ok=${result.ok}`);
      console.log(`build_id=${result.buildId}`);
      console.log(`build_ready=${result.quality.build_ready}`);
      console.log(`drc_pass=${result.quality.drc_pass}`);
    }
    process.exit(result.ok ? 0 : 1);
  } catch (err) {
    const message = err && err.stack ? err.stack : String(err);
    if (args.json) {
      console.log(JSON.stringify({ ok: false, error: message }, null, 2));
    } else {
      console.error(message);
    }
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { compileBuild, compileGraph, compileFromGraphFile, SUPPORTED_BUILD_IDS };
