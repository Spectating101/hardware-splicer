"""Device-splice assessment feeds the existing repair/new-build work-package gates."""
import json
from pathlib import Path
import pytest
from hardware_splicer.real_device_work_package import compile_work_package

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "eval/device_splice_feasibility"

def test_real_steamdeck_case_exposes_unknown_interfaces_as_work_steps():
    case = json.loads((ROOT / "eval/real_hardware_projects/steamdeck_oled_ssd.json").read_text())
    review = json.loads((ROOT / "eval/real_hardware_projects/reports/steamdeck_oled_ssd.json").read_text())
    candidate = json.loads((FIX / "steamdeck_oled_ssd.json").read_text())
    result = compile_work_package(case, review, planner=review["hs_raw_plan"], splice_candidate=candidate)
    assert result["device_splice_feasibility"]["overall_status"] == "unknown"
    assert len([x for x in result["work_steps"] if "interface_id" in x]) == 5
    assert len([x for x in result["critical_unknowns"] if "interface_id" in x]) == 5
    assert result["engineering_readiness"] == "blocked"
    assert not result["build_or_repair_completed"]

def test_synthetic_build_adds_regulator_validation_and_physical_gate():
    candidate = json.loads((FIX / "controller_display_demo.json").read_text())
    case = {"id": "demo-device", "device": "Controller display enclosure", "kind": "new_build",
            "deliverables": ["wiring plan", "mounting drawing"], "acceptance": ["power limited bench test"]}
    review = {"operator_casefile": {"build_or_repair_sequence": ["Inspect board"],
              "critical_technical_unknowns": ["Unmeasured enclosure tolerances"],
              "compatible_parts_or_requirements": ["Regulator module"]}}
    package = compile_work_package(case, review, splice_candidate=candidate)
    assert package["device_splice_feasibility"]["overall_status"] == "adaptable_pending_validation"
    assert any(row.get("interface_id") == "display_power" for row in package["work_steps"])
    assert any("actual 3D fit" in row["criterion"] for row in package["acceptance_gates"])
    assert package["engineering_readiness"] == "blocked"

def test_invalid_interface_reference_rejected_before_work_package():
    candidate = json.loads((FIX / "controller_display_demo.json").read_text())
    candidate["interfaces"][0]["to"] = "not_in_components"
    with pytest.raises(ValueError):
        compile_work_package({"id": "x", "device": "x", "kind": "new_build"}, {}, splice_candidate=candidate)
