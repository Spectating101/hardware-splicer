#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Geometry-only compiler: build_graph.json → DRC-clean KiCad PCB.
 * Used by the Python engine after plan_to_graph.py (no plan-to-graph.ts dependency).
 */
const fs = require("fs");
const path = require("path");
const Module = require("module");

const ROOT = path.resolve(__dirname, "..");
const FRONTEND = path.join(ROOT, "apps/circuit-ai/circuit-ai-frontend");
const CATALOG_DATA = path.join(ROOT, "src/hardware_splicer/data/catalog_recipes.json");

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
const { buildGraphToGeometry } = require(path.join(FRONTEND, "lib/pcb/build-to-geometry.ts"));
const { runDrc } = require(path.join(FRONTEND, "lib/pcb/drc.ts"));
const { serializeBuildToKicadPcb } = require(path.join(FRONTEND, "lib/kicad-serializer.ts"));

function loadSupportedBuildIds() {
  if (!fs.existsSync(CATALOG_DATA)) return [];
  try {
    const raw = JSON.parse(fs.readFileSync(CATALOG_DATA, "utf8"));
    return Array.isArray(raw.supported_build_ids) ? raw.supported_build_ids : [];
  } catch {
    return [];
  }
}

function loadBuildGraphMeta(metaPath) {
  if (!metaPath || !fs.existsSync(metaPath)) {
    return { notes: [], warnings: [], effectiveBuildId: null };
  }
  try {
    const raw = JSON.parse(fs.readFileSync(metaPath, "utf8"));
    return {
      notes: Array.isArray(raw.notes) ? raw.notes : [],
      warnings: Array.isArray(raw.warnings) ? raw.warnings : [],
      effectiveBuildId: raw.build_id || raw.effective_build_id || null,
    };
  } catch {
    return { notes: [], warnings: [], effectiveBuildId: null };
  }
}

function compileGraph(buildId, outDir, graph, notes, warnings, effectiveBuildId) {
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

  const resolvedBuildId = effectiveBuildId || buildId;
  const quality = {
    schema_version: "hardware_splicer.design_quality.v1",
    build_id: resolvedBuildId,
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
    supported_build_ids: loadSupportedBuildIds(),
    geometry_engine: "node_pcb_stack",
  };

  fs.writeFileSync(qualityPath, JSON.stringify(quality, null, 2));

  return {
    ok: buildReady,
    buildId: resolvedBuildId,
    outDir,
    paths: {
      build_graph: buildGraphPath,
      kicad_pcb: kicadText ? kicadPath : null,
      design_quality: qualityPath,
    },
    quality,
  };
}

function compileFromGraphFile(buildId, outDir, buildGraphPath, buildGraphMetaPath) {
  const graph = JSON.parse(fs.readFileSync(buildGraphPath, "utf8"));
  const meta = loadBuildGraphMeta(buildGraphMetaPath);
  return compileGraph(
    buildId,
    outDir,
    graph,
    meta.notes,
    meta.warnings,
    meta.effectiveBuildId || buildId,
  );
}

function parseArgs(argv) {
  const out = {
    buildId: null,
    outDir: null,
    buildGraphPath: null,
    buildGraphMetaPath: null,
    json: false,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--json") out.json = true;
    else if (arg === "--build-id" && argv[i + 1]) out.buildId = argv[++i];
    else if (arg === "--out" && argv[i + 1]) out.outDir = argv[++i];
    else if (arg === "--build-graph" && argv[i + 1]) out.buildGraphPath = argv[++i];
    else if (arg === "--build-graph-meta" && argv[i + 1]) out.buildGraphMetaPath = argv[++i];
  }
  return out;
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.buildId || !args.outDir || !args.buildGraphPath) {
    console.error(
      "Usage: node scripts/compile_geometry.cjs --build-id <id> --out <dir> " +
        "--build-graph <path> [--build-graph-meta <path>] [--json]",
    );
    process.exit(2);
  }
  try {
    const result = compileFromGraphFile(
      args.buildId,
      path.resolve(args.outDir),
      path.resolve(args.buildGraphPath),
      args.buildGraphMetaPath,
    );
    if (args.json) {
      console.log(JSON.stringify(result, null, 2));
    } else {
      console.log(`ok=${result.ok}`);
      console.log(`build_id=${result.buildId}`);
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

module.exports = { compileGraph, compileFromGraphFile, loadBuildGraphMeta };
