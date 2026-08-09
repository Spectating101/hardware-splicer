"""DRC fix loop and salvage bring-up tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hardware_splicer.pcb.drc_fix_loop import (
    apply_fixup_to_graph,
    classify_violation,
    propose_fixup_hints,
    compile_with_drc_fixup_loop,
)
from hardware_splicer.pcb.geometry_compile import compile_graph_to_artifacts
from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.repair_policy import repair_policy_report

ROOT = Path(__file__).resolve().parents[1]


def test_classify_clearance_violation() -> None:
    row = {"type": "clearance", "description": "Clearance violation", "severity": "error"}
    assert classify_violation(row) == "clearance"


def test_propose_fixup_hints_accumulates() -> None:
    violations = [
        {"type": "clearance", "severity": "error", "description": "Clearance"},
        {"type": "edge_clearance", "severity": "error", "description": "Edge"},
    ]
    hints = propose_fixup_hints(violations, {})
    assert hints["via_clearance_mm"] > 0.21
    assert hints["edge_pad_extra_mm"] > 0


def test_repair_policy_rejects_identity_or_architecture_mutation_channels() -> None:
    with pytest.raises(ValueError, match="outside geometry authority"):
        repair_policy_report({"module_id": 1})
    with pytest.raises(ValueError, match="outside geometry authority"):
        repair_policy_report({"recommended_build_id": 1})
    with pytest.raises(ValueError, match="outside geometry authority"):
        repair_policy_report({"net_topology": 1})


def test_apply_fixup_changes_only_drc_geometry_surface() -> None:
    graph = {
        "build_id": "generic_low_voltage_build",
        "modules": [
            {"role": "mcu", "module_id": "esp32-devkit"},
            {"role": "sensor", "module_id": "dht22"},
        ],
        "nets": [{"name": "DATA", "pins": ["mcu.GPIO4", "sensor.DATA"]}],
    }
    original = copy.deepcopy(graph)

    apply_fixup_to_graph(
        graph,
        {
            "edge_pad_extra_mm": 0.35,
            "via_clearance_mm": 0.27,
            "module_gap_extra_mm": 4.0,
        },
    )

    assert graph["build_id"] == original["build_id"]
    assert graph["modules"] == original["modules"]
    assert graph["nets"] == original["nets"]
    assert graph["drc_fixup"] == {
        "edge_pad_extra_mm": 0.35,
        "via_clearance_mm": 0.27,
        "module_gap_extra_mm": 4.0,
    }


def test_repair_policy_never_opens_physical_authority() -> None:
    report = repair_policy_report({"via_clearance_mm": 0.27})
    assert report["component_identity_mutation_allowed"] is False
    assert report["module_override_mutation_allowed"] is False
    assert report["net_topology_mutation_allowed"] is False
    assert report["architecture_selection_allowed"] is False
    assert report["fabrication_authorized"] is False
    assert report["power_on_authorized"] is False
    assert report["motion_authorized"] is False
    assert report["authority_effect"] == "none"


def test_drc_fix_loop_records_attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    graph = compose_build_graph_from_module_ids(["usb-power-5v", "esp32-devkit", "dht22"])["graph"]
    payload = compile_with_drc_fixup_loop(
        compile_graph_to_artifacts,
        "generic_low_voltage_build",
        tmp_path,
        graph,
    )
    loop = (payload.get("quality") or {}).get("drc_fix_loop") or {}
    assert loop.get("enabled") is True
    assert len(loop.get("attempts") or []) >= 1
    assert loop["repair_policy"]["architecture_selection_allowed"] is False
    assert loop["repair_policy"]["component_identity_mutation_allowed"] is False
    assert loop["authority_effect"] == "none"
    assert loop["fabrication_authorized"] is False
    assert (tmp_path / "DRC_FIX_LOOP.json").is_file()
    assert int((payload.get("quality") or {}).get("kicad_drc_errors") or 0) == 0


@pytest.mark.skipif(
    not (ROOT / "examples" / "intakes" / "salvage_wifi_logger_brief.json").is_file(),
    reason="salvage intake missing",
)
def test_salvage_bringup_demo_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    from hardware_splicer.salvage_bringup import run_salvage_bringup

    intake = json.loads(
        (ROOT / "examples" / "intakes" / "salvage_wifi_logger_brief.json").read_text(encoding="utf-8")
    )
    report = run_salvage_bringup(intake, out_dir=tmp_path, export_gerber=False)
    assert report["salvage_mode"] is True
    assert (tmp_path / "SALVAGE_BRINGUP_REPORT.json").is_file()

    drc_errors = report["quality_summary"].get("kicad_drc_errors")
    if drc_errors is None:
        # Dependency-light CI cannot claim a clean DRC receipt. The dedicated
        # KiCad workflow remains the positive compile bar.
        assert report["ok"] is False
    else:
        assert drc_errors == 0
        assert report["ok"] is True
