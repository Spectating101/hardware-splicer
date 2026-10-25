"""An agent reads a build through one tool call. The verdict it needs is small; the full result is not."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.graph_patch import apply_graph_patch
from hardware_splicer.pcb.safety_rules import analyze_build
from hardware_splicer.product_api import create_product_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "0")
    return TestClient(create_product_app())


def _intake(module_ids: list[str]) -> dict:
    return {
        "project_name": "verdict_case",
        "goal": f"Build a board with exactly these parts: {', '.join(module_ids)}.",
        "salvage_mode": True,
        "available_parts": [
            {"name": f"{mid} {i}", "module_id": mid, "type": "part", "condition": "salvaged"} for i, mid in enumerate(module_ids)
        ],
        "constraints": {"strategy_mode": "constrained", "prefer_salvage": True},
    }


THREE_SENSORS = ["esp32-devkit", "bme280", "bme280", "bme280", "usb-power-5v"]


def test_a_compact_build_is_a_small_verdict_and_the_default_is_still_the_full_result(client) -> None:
    full = client.post("/v1/splice-and-build", json={"intake": _intake(THREE_SENSORS), "export_gerber": False}).json()
    compact = client.post("/v1/splice-and-build", json={"intake": _intake(THREE_SENSORS), "export_gerber": False, "compact": True}).json()

    assert "salvage_package" in full
    assert "salvage_package" not in compact
    assert len(json.dumps(compact)) < 6000 < len(json.dumps(full)) / 10
    assert compact["schema_version"] == "hardware_splicer.agent_verdict.v1"
    assert (compact["ok"], compact["build_ready"]) == (full["ok"], full["design_quality_gate"]["build_ready"])


def test_the_verdict_carries_what_an_agent_needs_to_decide_what_to_do(client) -> None:
    verdict = client.post(
        "/v1/splice-and-build", json={"intake": _intake(THREE_SENSORS), "export_gerber": False, "compact": True}
    ).json()

    assert verdict["build_ready"] is False
    assert any("0x77" in b and "cannot both work" in b for b in verdict["blockers"])
    [finding] = verdict["repairable_findings"]
    assert finding["code"] == "i2c_address_clash"
    [repair] = finding["repairs"]
    assert repair["kind"] == "strap_alternate_address" and repair["requires_person"] is True
    assert verdict["request_fidelity"]["status"] == "matches"
    assert verdict["firmware_coverage"]["status"] in {"gaps", "not_assessable", "covers"}
    assert verdict["physical_correctness"] == "UNPROVEN"
    assert verdict["out_dir"]


def test_things_only_a_person_can_do_are_listed_apart_from_what_the_agent_can_fix(client) -> None:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "bme280", "usb-power-5v"], auto_repair=False)["graph"]
    clash = next(w for w in analyze_build(graph) if w.get("code") == "i2c_address_clash")
    strapped = apply_graph_patch(graph, next(r for r in clash["repairs"] if r["kind"] == "strap_alternate_address")["graph_patch"])

    verdict = client.post(
        "/v1/compose-canvas", json={"nodes": strapped["nodes"], "wires": strapped["wires"], "export_gerber": False, "compact": True}
    ).json()

    assert verdict["schema_version"] == "hardware_splicer.agent_verdict.v1"
    [step] = verdict["needs_a_person"]
    assert "address" in step["message"] and step["node"]


def test_the_canvas_path_returns_a_compact_verdict_the_agent_can_act_on(client) -> None:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "bme280", "usb-power-5v"], auto_repair=False)["graph"]

    verdict = client.post(
        "/v1/compose-canvas", json={"nodes": graph["nodes"], "wires": graph["wires"], "export_gerber": False, "compact": True}
    ).json()

    assert verdict["ok"] is False and verdict["build_ready"] is False
    kinds = {r["kind"] for f in verdict["repairable_findings"] for r in f["repairs"]}
    assert kinds == {"second_i2c_bus", "strap_alternate_address"}
    assert len(json.dumps(verdict)) < 7000


GENERIC = "Electrical safety checks failed on the compiled build graph."


def test_the_verdict_drops_the_generic_failure_line_when_specific_findings_explain_it(client) -> None:
    verdict = client.post(
        "/v1/splice-and-build", json={"intake": _intake(THREE_SENSORS), "export_gerber": False, "compact": True}
    ).json()

    assert GENERIC not in verdict["blockers"]
    assert any("cannot both work" in b for b in verdict["blockers"])


def test_the_verdict_keeps_the_generic_line_when_nothing_more_specific_is_known() -> None:
    from hardware_splicer.build_verdict import agent_verdict

    verdict = agent_verdict({"ok": False, "design_quality_gate": {"blockers": [GENERIC], "summary": {"electrical_issues": []}}})

    assert verdict["blockers"] == [GENERIC]


def test_the_full_gate_still_carries_the_generic_line_for_the_records_that_read_it() -> None:
    from hardware_splicer.design_quality import build_design_quality_gate

    gate = build_design_quality_gate(
        {"build_graph_compiled": True, "electrical_safety_pass": False, "drc_pass": True,
         "electrical_issues": [{"level": "error", "message": "two devices clash", "code": "i2c_address_clash"}]}
    )

    assert GENERIC in gate["blockers"] and "two devices clash" in gate["blockers"]
