from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hardware_splicer.catalog import CATALOG_BUILD_IDS
from hardware_splicer.plan_to_graph import splice_plan_to_build_graph, supported_build_ids


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "apps" / "circuit-ai" / "circuit-ai-frontend"
PLAN_TO_GRAPH = FRONTEND / "lib" / "salvage" / "plan-to-graph.ts"


def _ts_splice_plan_to_graph(plan: dict) -> dict:
    """Invoke splicePlanToBuildGraph in TS for golden parity."""
    script = f"""
const path = require("path");
const fs = require("fs");
const Module = require("module");
const FRONTEND = {json.dumps(str(FRONTEND))};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, isMain, options) {{
  if (request.startsWith("@/")) {{
    return originalResolve.call(this, path.join(FRONTEND, request.slice(2)), parent, isMain, options);
  }}
  return originalResolve.call(this, request, parent, isMain, options);
}};
const TS_LIB = path.join(FRONTEND, "node_modules", "typescript", "lib", "typescript.js");
const ts = fs.existsSync(TS_LIB) ? require(TS_LIB) : require("typescript");
require.extensions[".ts"] = (mod, filename) => {{
  const source = fs.readFileSync(filename, "utf8");
  mod._compile(ts.transpileModule(source, {{
    compilerOptions: {{ module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019, esModuleInterop: true }},
  }}).outputText, filename);
}};
const {{ splicePlanToBuildGraph }} = require({json.dumps(str(PLAN_TO_GRAPH))});
const plan = JSON.parse(process.argv[1]);
const result = splicePlanToBuildGraph(plan);
process.stdout.write(JSON.stringify(result.graph));
"""
    proc = subprocess.run(
        ["node", "-e", script, json.dumps(plan)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def test_supported_build_ids_match_catalog() -> None:
    assert supported_build_ids() == CATALOG_BUILD_IDS


@pytest.mark.parametrize("build_id", CATALOG_BUILD_IDS)
def test_python_graph_matches_typescript_recipe(build_id: str) -> None:
    plan = {"target": {"recommended_build_id": build_id}}
    py_graph, _, _, py_warnings = splice_plan_to_build_graph(plan)
    assert py_graph.get("nodes"), f"empty graph for {build_id}: {py_warnings}"

    if not PLAN_TO_GRAPH.is_file() or not shutil.which("node"):
        pytest.skip("node or plan-to-graph.ts unavailable")

    ts_graph = _ts_splice_plan_to_graph(plan)
    assert py_graph == ts_graph, build_id


@pytest.mark.parametrize("build_id", CATALOG_BUILD_IDS)
def test_usb_plant_watering_topology_variant(build_id: str) -> None:
    if build_id != "automatic_plant_watering":
        return
    plan = {
        "target": {"recommended_build_id": "automatic_plant_watering"},
        "power_topology": "usb_5v",
    }
    py_graph, effective_id, _, _ = splice_plan_to_build_graph(plan)
    assert effective_id == "automatic_plant_watering"
    module_ids = {n["moduleId"] for n in py_graph["nodes"]}
    assert "usb-power-5v" in module_ids
    assert "dc-barrel-12v" not in module_ids
    assert "buck-mp1584" not in module_ids
