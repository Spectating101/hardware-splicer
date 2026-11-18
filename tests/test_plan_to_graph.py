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
TS_LIB = FRONTEND / "node_modules" / "typescript" / "lib" / "typescript.js"


def _typescript_runtime_path() -> str | None:
    """Return the exact TypeScript runtime the parity subprocess can load."""
    if TS_LIB.is_file():
        return str(TS_LIB)
    if not shutil.which("node"):
        return None
    probe = subprocess.run(
        ["node", "-e", "process.stdout.write(require.resolve('typescript'))"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    resolved = probe.stdout.strip()
    return resolved or None


def _ts_splice_plan_to_graph(plan: dict, *, typescript_runtime: str) -> dict:
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
const ts = require({json.dumps(str(typescript_runtime))});
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
    typescript_runtime = _typescript_runtime_path()
    if not typescript_runtime:
        pytest.skip("TypeScript runtime unavailable in this Python-only test environment")

    ts_graph = _ts_splice_plan_to_graph(plan, typescript_runtime=typescript_runtime)
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


def _assert_no_reserved_wires(graph: dict) -> None:
    from hardware_splicer.pcb.module_registry import find_module

    specs = {n["id"]: find_module(n["moduleId"]) for n in graph["nodes"]}
    for wire in graph["wires"]:
        for end in (wire["from"], wire["to"]):
            spec = specs[end["nodeId"]]
            assert spec
            pin = next((p for p in spec["pins"] if p["id"] == end["pinId"]), None)
            assert pin and not pin.get("reserved"), (spec["id"], end["pinId"])


@pytest.mark.parametrize("build_id", ["inspection_motion_fixture", "sensor_logger"])
def test_esp32_cam_inventory_builds_do_not_use_psram_gpio(build_id: str) -> None:
    plan = {
        "target": {"recommended_build_id": build_id},
        "power_topology": "usb_5v",
        "module_overrides": {"mcu": "esp32-cam-module", "sns": "dht22"},
        "resolved_modules": [
            {"role": "mcu", "module_id": "esp32-cam-module"},
            {"role": "usb", "module_id": "usb-power-5v"},
            {"role": "svo", "module_id": "sg90"},
            {"role": "svo2", "module_id": "sg90"},
            {"role": "sns", "module_id": "dht22"},
        ],
    }
    graph, _, _, _ = splice_plan_to_build_graph(plan)
    _assert_no_reserved_wires(graph)
    nodes = {n["id"]: n["moduleId"] for n in graph["nodes"]}
    control_pins = {"DATA"} if build_id == "sensor_logger" else {"SIG"}
    controls = [w for w in graph["wires"] if w["to"]["pinId"] in control_pins]
    assert controls
    for wire in controls:
        assert nodes[wire["from"]["nodeId"]] == "esp32-cam-module"
        assert wire["from"]["pinId"] != "GPIO16"


@pytest.mark.parametrize("mcu_id", ["esp32-cam-module", "esp32-devkit", "arduino-nano"])
def test_typescript_auto_wire_never_uses_reserved_pins(mcu_id: str) -> None:
    runtime = _typescript_runtime_path()
    if not runtime:
        pytest.skip("Node/TypeScript runtime unavailable")
    plan = {
        "target": {"recommended_build_id": "sensor_logger"},
        "compose_from_inventory": True,
        "resolved_modules": [{"module_id": mid} for mid in [
            mcu_id, "usb-power-5v", "sg90", "dht22", "hc-sr04", "l298n", "a4988-stepper",
        ]],
    }
    graph = _ts_splice_plan_to_graph(plan, typescript_runtime=runtime)
    assert graph["wires"]
    _assert_no_reserved_wires(graph)


@pytest.mark.parametrize("compiler", ["compile_geometry.cjs", "compile_build_graph.cjs"])
def test_node_and_python_withhold_fabrication_for_unverified_usb_fit(tmp_path: Path, compiler: str) -> None:
    from hardware_splicer.pcb.geometry_compile import compile_graph_to_artifacts

    runtime = _typescript_runtime_path()
    if not runtime:
        pytest.skip("Node/TypeScript runtime unavailable")
    graph = {
        "nodes": [{"id": "pwr", "moduleId": "usb-power-5v"}, {"id": "sns", "moduleId": "hc-sr04"}],
        "wires": [
            {"id": "w1", "from": {"nodeId": "pwr", "pinId": "V+"}, "to": {"nodeId": "sns", "pinId": "VCC"}},
            {"id": "w2", "from": {"nodeId": "pwr", "pinId": "GND"}, "to": {"nodeId": "sns", "pinId": "GND"}},
        ],
    }
    py_quality = compile_graph_to_artifacts("custom", tmp_path / "python", graph)["quality"]
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    proc = subprocess.run(
        ["node", str(ROOT / "scripts" / compiler), "--build-id", "custom", "--out", str(tmp_path / "node"),
         "--build-graph", str(graph_path), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    node_quality = json.loads(proc.stdout)["quality"]
    assert py_quality["build_ready"] and node_quality["build_ready"]
    assert node_quality["fabrication_ready"] == py_quality["fabrication_ready"] == False
    assert node_quality["unverified_fit_modules"] == py_quality["unverified_fit_modules"] == ["usb-power-5v"]
