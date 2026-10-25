"""An agent can only act on what HS tells it. The structured finding and its repairs must survive
into the compile result and the quality gate, and the gate must say what is wrong in words."""

from __future__ import annotations

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.canvas_compose import compile_canvas_build
from hardware_splicer.design_quality import build_design_quality_gate

TWO_SENSORS = ["esp32-devkit", "bme280", "bme280", "usb-power-5v"]


def _quality(tmp_path) -> dict:
    graph = compose_build_graph_from_module_ids(TWO_SENSORS)["graph"]
    result = compile_canvas_build(out_dir=str(tmp_path / "b"), nodes=graph["nodes"], wires=graph["wires"], export_gerber=False)
    return result.compile_result.design_quality


def test_the_compile_result_keeps_the_code_the_nodes_and_the_repairs(tmp_path) -> None:
    issues = _quality(tmp_path)["electrical_issues"]
    [clash] = [i for i in issues if i.get("code") == "i2c_address_clash"]

    assert clash["level"] == "error"
    assert clash["address"] == "0x77" and len(clash["nodes"]) == 2
    kinds = {r["kind"] for r in clash["repairs"]}
    assert kinds == {"second_i2c_bus", "strap_alternate_address"}
    assert clash["repairs"][0]["graph_patch"]["add_wires"]


def test_existing_issue_entries_keep_their_old_shape(tmp_path) -> None:
    issues = _quality(tmp_path)["electrical_issues"]
    plain = next(i for i in issues if i.get("code") is None)

    assert set(plain) == {"level", "message", "wire_id", "node_id"}


def test_the_gate_says_in_words_what_is_wrong_not_only_that_a_check_failed(tmp_path) -> None:
    gate = build_design_quality_gate(_quality(tmp_path))

    assert gate["build_ready"] is False
    assert any("0x77" in blocker and "cannot both work" in blocker for blocker in gate["blockers"])


def test_the_gate_hands_the_agent_the_repairable_findings_directly(tmp_path) -> None:
    gate = build_design_quality_gate(_quality(tmp_path))

    [finding] = gate["repairable_findings"]
    assert finding["code"] == "i2c_address_clash" and finding["repairs"]


def test_a_gate_with_nothing_to_repair_has_an_empty_list_not_a_missing_key() -> None:
    gate = build_design_quality_gate({"build_graph_compiled": True, "electrical_safety_pass": True, "drc_pass": True, "build_ready": True})

    assert gate["repairable_findings"] == []
