"""A finding only a person can clear (a strap HS cannot see) must stop the design reading as build-ready
everywhere: in DESIGN_QUALITY.json, in the compile result, and in the gate. The file and the gate agree."""

from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.canvas_compose import compile_canvas_build
from hardware_splicer.design_quality import build_design_quality_gate
from hardware_splicer.graph_patch import apply_graph_patch
from hardware_splicer.pcb.safety_rules import analyze_build


def _strapped() -> dict:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "bme280", "usb-power-5v"], auto_repair=False)["graph"]
    clash = next(w for w in analyze_build(graph) if w.get("code") == "i2c_address_clash")
    return apply_graph_patch(graph, next(r for r in clash["repairs"] if r["kind"] == "strap_alternate_address")["graph_patch"])


def _unknown_twins() -> dict:
    return compose_build_graph_from_module_ids(["esp32-devkit", "bmp280", "bmp280", "usb-power-5v"], auto_repair=False)["graph"]


def _compile(tmp_path, graph):
    return compile_canvas_build(out_dir=str(tmp_path / "b"), nodes=graph["nodes"], wires=graph["wires"], export_gerber=False)


def test_the_quality_file_does_not_say_build_ready_for_a_strapped_design(tmp_path, assume_clean_kicad_erc) -> None:
    result = _compile(tmp_path, _strapped())
    on_disk = json.loads((Path(result.compile_result.design_quality_file)).read_text())

    assert on_disk["electrical_errors"] == 0 and on_disk["drc_pass"] is True
    assert on_disk["build_ready"] is False
    assert on_disk["circuit_readiness"] != "build_ready"
    assert result.compile_result.ok is False


def test_the_file_and_the_gate_agree_for_a_strapped_design(tmp_path, assume_clean_kicad_erc) -> None:
    quality = _compile(tmp_path, _strapped()).compile_result.design_quality
    gate = build_design_quality_gate(quality)

    assert gate["build_ready"] is quality["build_ready"] is False
    assert gate["circuit_readiness"] != "build_ready"


def test_any_needs_a_person_finding_blocks_not_only_a_strap(tmp_path, assume_clean_kicad_erc) -> None:
    quality = _compile(tmp_path, _unknown_twins()).compile_result.design_quality
    gate = build_design_quality_gate(quality)

    assert any(i.get("requires_person") for i in quality["electrical_issues"])
    assert quality["build_ready"] is False
    assert gate["build_ready"] is False and gate["circuit_readiness"] != "build_ready"


def test_a_gate_given_a_ready_file_with_a_person_finding_still_says_not_ready() -> None:
    gate = build_design_quality_gate(
        {"build_graph_compiled": True, "electrical_safety_pass": True, "drc_pass": True, "build_ready": True,
         "electrical_warnings": 1,
         "electrical_issues": [{"level": "warn", "message": "set the pin", "requires_person": True}]}
    )

    assert gate["build_ready"] is False and gate["circuit_readiness"] != "build_ready"


def test_a_repaired_design_with_no_person_step_is_still_build_ready(tmp_path, assume_clean_kicad_erc) -> None:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "bme280", "usb-power-5v"], auto_repair=True)["graph"]

    assert _compile(tmp_path, graph).compile_result.design_quality["build_ready"] is True
