#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Headless build compiler: catalog build_id -> DRC-clean KiCad PCB + design quality JSON.
 * Used by the Python hardware_splicer build_compiler module (backend Path B).
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

const { analyzeBuild } = require(path.join(FRONTEND, "lib/rules/safety-rules.ts"));
const { splicePlanToBuildGraph, SUPPORTED_BUILD_IDS } = require(path.join(
  FRONTEND,
  "lib/salvage/plan-to-graph.ts",
));
const { buildGraphToGeometry } = require(path.join(FRONTEND, "lib/pcb/build-to-geometry.ts"));
const { runDrc } = require(path.join(FRONTEND, "lib/pcb/drc.ts"));
const { serializeBuildToKicadPcb } = require(path.join(FRONTEND, "lib/kicad-serializer.ts"));

function parseArgs(argv) {
  const out = { buildId: null, outDir: null, splicePlanPath: null, json: false };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--json") out.json = true;
    else if (arg === "--build-id" && argv[i + 1]) {
      out.buildId = argv[++i];
    } else if (arg === "--out" && argv[i + 1]) {
      out.outDir = argv[++i];
    } else if (arg === "--splice-plan" && argv[i + 1]) {
      out.splicePlanPath = argv[++i];
    }
  }
  return out;
}

function loadSplicePlan(path, buildId) {
  if (!path) return { target: { recommended_build_id: buildId } };
  const raw = JSON.parse(fs.readFileSync(path, "utf8"));
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
  const electrical = analyzeBuild(graph);
  const electricalErrors = electrical.filter((w) => w.level === "error");
  const electricalWarnings = electrical.filter((w) => w.level === "warn");

  let geometry = null;
  let drc = null;
  let kicadText = "";
  if (graph.nodes.length > 0) {
    geometry = buildGraphToGeometry(graph);
    drc = runDrc(geometry);
    kicadText = serializeBuildToKicadPcb(graph, geometry);
  } else {
    drc = {
      pass: false,
      violations: [{ rule: "trace-short", severity: "error", message: "Empty build graph" }],
      summary: { errors: 1, warnings: 0, byRule: { empty: 1 } },
    };
  }

  const drcErrors = (drc.violations || []).filter((v) => v.severity === "error").length;
  const fabricationReady =
    graph.nodes.length > 0 &&
    electricalErrors.length === 0 &&
    electricalWarnings.length === 0 &&
    drc.pass === true &&
    Boolean(kicadText && kicadText.includes("(kicad_pcb"));

  const buildReady =
    graph.nodes.length > 0 &&
    electricalErrors.length === 0 &&
    drc.pass === true &&
    Boolean(kicadText && kicadText.includes("(kicad_pcb"));

  fs.mkdirSync(outDir, { recursive: true });
  const buildGraphPath = path.join(outDir, "build_graph.json");
  const kicadPath = path.join(outDir, "main_ctrl_build.kicad_pcb");
  const qualityPath = path.join(outDir, "DESIGN_QUALITY.json");

  fs.writeFileSync(buildGraphPath, JSON.stringify(graph, null, 2));
  if (kicadText) {
    fs.writeFileSync(kicadPath, kicadText, "utf8");
  }

  const bbox = geometry?.board?.bbox_mm ?? null;
  const boardOutline = geometry
    ? {
        width_mm: bbox?.width ?? geometry.board?.width_mm ?? null,
        height_mm: bbox?.height ?? geometry.board?.height_mm ?? null,
        bbox_mm: bbox,
        footprint_count: (geometry.footprints || []).length,
        trace_segments: (geometry.segments || []).length,
        via_count: (geometry.vias || []).length,
      }
    : null;

  const quality = {
    schema_version: "hardware_splicer.design_quality.v1",
    build_id: effectiveBuildId || buildId,
    build_ready: buildReady,
    fabrication_ready: fabricationReady,
    build_graph_compiled: graph.nodes.length > 0,
    electrical_safety_pass: electricalErrors.length === 0,
    drc_pass: drc.pass === true,
    drc_errors: drcErrors,
    drc_warnings: drc.summary?.warnings ?? 0,
    electrical_errors: electricalErrors.length,
    electrical_warnings: electricalWarnings.length,
    circuit_readiness: buildReady ? "build_ready" : "blocked",
    gerber_ready: false,
    kicad_pcb_path: kicadText ? kicadPath : null,
    board_outline: boardOutline,
    module_count: graph.nodes.length,
    wire_count: graph.wires.length,
    notes,
    warnings: [...warnings, ...electricalWarnings.map((w) => w.message)],
    electrical_issues: electrical.map((w) => ({
      level: w.level,
      message: w.message,
      wire_id: w.wireId,
      node_id: w.nodeId,
    })),
    drc_violations: drc.violations || [],
    supported_build_ids: SUPPORTED_BUILD_IDS,
  };

  fs.writeFileSync(qualityPath, JSON.stringify(quality, null, 2));

  return {
    ok: buildReady,
    buildId,
    outDir,
    paths: {
      build_graph: buildGraphPath,
      kicad_pcb: kicadText ? kicadPath : null,
      design_quality: qualityPath,
    },
    quality,
  };
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.buildId || !args.outDir) {
    console.error("Usage: node scripts/compile_build_graph.cjs --build-id <id> --out <dir> [--json]");
    process.exit(2);
  }
  try {
    const result = compileBuild(args.buildId, path.resolve(args.outDir), args.splicePlanPath);
    if (args.json) {
      console.log(JSON.stringify(result, null, 2));
    } else {
      console.log(`ok=${result.ok}`);
      console.log(`build_id=${result.buildId}`);
      console.log(`build_ready=${result.quality.build_ready}`);
      console.log(`drc_pass=${result.quality.drc_pass}`);
      console.log(`kicad_pcb=${result.paths.kicad_pcb || ""}`);
      console.log(`design_quality=${result.paths.design_quality}`);
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

module.exports = { compileBuild, SUPPORTED_BUILD_IDS };
