#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Fail if Python CATALOG_BUILD_IDS diverges from TS SUPPORTED_BUILD_IDS.
 */
const { spawnSync } = require("child_process");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const compileScript = path.join(__dirname, "compile_build_graph.cjs");

function loadPythonCatalog() {
  const proc = spawnSync(
    "python3",
    [
      "-c",
      "import json; from hardware_splicer.catalog import CATALOG_BUILD_IDS; print(json.dumps(CATALOG_BUILD_IDS))",
    ],
    { cwd: ROOT, env: { ...process.env, PYTHONPATH: path.join(ROOT, "src") }, encoding: "utf8" },
  );
  if (proc.status !== 0) {
    console.error(proc.stderr || proc.stdout || "failed to load Python catalog");
    process.exit(1);
  }
  return JSON.parse(proc.stdout.trim());
}

function loadTsCatalog() {
  const proc = spawnSync("node", [compileScript, "--list-build-ids"], {
    cwd: ROOT,
    encoding: "utf8",
  });
  if (proc.status !== 0) {
    console.error(proc.stderr || proc.stdout || "failed to load TS catalog");
    process.exit(1);
  }
  return JSON.parse(proc.stdout.trim());
}

function main() {
  const pythonIds = new Set(loadPythonCatalog());
  const tsIds = new Set(loadTsCatalog());

  const onlyPython = [...pythonIds].filter((id) => !tsIds.has(id)).sort();
  const onlyTs = [...tsIds].filter((id) => !pythonIds.has(id)).sort();

  if (onlyPython.length || onlyTs.length) {
    console.error("Catalog parity check FAILED");
    if (onlyPython.length) {
      console.error("  only in Python catalog.py:", onlyPython.join(", "));
    }
    if (onlyTs.length) {
      console.error("  only in TS SUPPORTED_BUILD_IDS:", onlyTs.join(", "));
    }
    process.exit(1);
  }

  console.log(`Catalog parity OK (${pythonIds.size} build IDs)`);
}

main();
