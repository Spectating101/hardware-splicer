"""Circuit failures must survive promotion from compiler output to project claims."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from hardware_splicer.project_intake import load_project_intake, run_project_intake
from hardware_splicer.scenario_runner import build_project_authority_packet
from hardware_splicer.schemas import HardwareCompileResult, HardwareCompileSpec


def _release_result(tmp_path, quality, stored_gate=None):
    compilation = {"design_quality": quality}
    if stored_gate is not None:
        compilation["design_quality_gate"] = stored_gate
    return HardwareCompileResult(
        ok=True, project_name="circuit-gate", request_id="gate-test", generated_at="2026-11-16T00:00:00Z",
        out_dir=str(tmp_path), bundle_file="", report_file="", summary_file="", manifest_file="", metadata_file="",
        engineering={"build_compilation": compilation},
        robotics_simulation={"simulation_ready": True},
        robotics_platform_authority={"production_authorized": True, "current_authority_level": "production_robotics_project_release"},
        mechatronics_authority={"production_authorized": True, "current_authority_level": "production_mechatronics_release"},
    )


def _clean_quality(**changes):
    return {
        "build_id": "sensor_logger", "build_graph_compiled": True,
        "build_ready": True, "fabrication_ready": True, "compiler_verified": True,
        "drc_pass": True, "electrical_safety_pass": True,
        "kicad_erc_pass": True, "kicad_drc_pass": True,
        **changes,
    }


def _packet(result):
    return build_project_authority_packet(
        {"acceptance": {"allowed_blockers": 99, "source_blockers_are_next_actions": True}},
        result=result, spec=HardwareCompileSpec(project_name="circuit-gate", machine={}),
    )


@pytest.mark.parametrize("fault,message", [
    ({"kicad_erc_pass": False, "kicad_erc_errors": 4}, "KiCad ERC failed with 4 error(s)"),
    ({"kicad_drc_pass": False, "kicad_drc_errors": 2}, "KiCad DRC failed with 2 error(s)"),
    ({"goal_covered_by_selected_design": False}, "goal_not_covered_by_selected_design"),
])
def test_failed_circuit_receipt_overrides_stale_positive_summary(tmp_path, fault, message):
    result = _release_result(tmp_path, _clean_quality(**fault), {"build_ready": True})
    packet = _packet(result)
    assert packet["claimable"] is False
    assert packet["project_authority_level"] != "production_ready_project_package"
    assert packet["release_decision"] == "evidence_required_before_project_claim"
    assert packet["dashboard"]["build_ready"] is False
    assert packet["dashboard"]["hardware_splicer_release"] is False
    assert any(message in blocker for blocker in packet["blockers"])
    assert not any("Defend" in capability and "claim" in capability for capability in packet["can"])
    assert not any("Defend scoped Hardware-Splicer release" in capability for capability in packet["can"])


def test_failed_stored_gate_is_not_overridden_by_raw_ready_flag(tmp_path):
    packet = _packet(_release_result(tmp_path, _clean_quality(), {
        "build_ready": False, "blockers": ["Design leaves out requested part mini-pump-5v"],
    }))
    assert packet["claimable"] is False
    assert any("requested part mini-pump-5v" in blocker for blocker in packet["blockers"])


def test_clean_circuit_and_scenarios_without_build_compilation_keep_their_claims(tmp_path):
    result = _release_result(tmp_path, _clean_quality())
    for candidate in [result, replace(result, engineering={})]:
        packet = _packet(candidate)
        assert packet["claimable"] is True
        assert packet["project_authority_level"] == "production_ready_project_package"


def test_unfinished_circuit_keeps_planning_scope_and_exposes_the_remaining_work(tmp_path):
    result = _release_result(tmp_path, _clean_quality(kicad_erc_pass=False, kicad_erc_errors=4))
    result = replace(result, robotics_simulation={"simulation_ready": False},
        robotics_platform_authority={"production_authorized": False, "current_authority_level": "control_safety_architecture"},
        mechatronics_authority={"production_authorized": False})
    packet = _packet(result)
    assert packet["claimable"] is True
    assert packet["project_authority_level"] == "control_safety_project_package"
    assert packet["dashboard"]["build_ready"] is False
    assert packet["dashboard"]["hardware_splicer_release"] is False
    circuit_check = next(row for row in packet["checks"] if row["id"] == "circuit_build_ready")
    assert circuit_check["passed"] is False
    assert circuit_check["severity"] == "warn"
    assert any("KiCad ERC failed with 4 error(s)" in action for action in packet["next_actions"])


def test_erc_failure_is_preserved_in_saved_intake_authority(tmp_path, monkeypatch):
    # A controlled failed native receipt exercises the whole intake path without
    # requiring CadQuery or relying on a particular KiCad version's error count.
    monkeypatch.setattr("hardware_splicer.netlist.compile.run_kicad_cli_erc", lambda *a, **k: {
        "pass": False, "skipped": False, "errors": 4, "warnings": 0, "violations": [], "report_path": None,
    })
    intake = load_project_intake("examples/intakes/plant_watering_evidence_pack.json")
    result = run_project_intake(intake, out_dir=tmp_path / "plant", start_splicer=False)
    assert result["compile_ok"] is True
    assert result["ok"] is False
    authority = result["project_authority"]
    assert authority["claimable"] is False
    assert authority["dashboard"]["build_ready"] is False
    assert result["production_release_metrics"]["production_ready"] is False
    assert "circuit_release" in result["production_release_metrics"]["evidence_gap_ids"]
    circuit = next(row for row in authority["checks"] if row["id"] == "circuit_build_ready")
    assert circuit["passed"] is False
    assert "KiCad ERC failed with 4 error(s)" in circuit["message"]
    assert circuit["message"] in authority["blockers"] + authority["next_actions"]
    saved = json.loads((tmp_path / "plant" / "PROJECT_AUTHORITY.json").read_text())
    assert saved["claimable"] is False
    assert saved["release_decision"] == authority["release_decision"]
    assert circuit in saved["checks"]
