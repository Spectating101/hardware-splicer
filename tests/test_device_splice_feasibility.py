"""Device assembly capability: grounded intake leads and synthetic new-build checks."""
import json
from pathlib import Path
import pytest
from hardware_splicer.device_splice_feasibility import assess_device_splice

ROOT = Path(__file__).resolve().parents[1] / "eval/device_splice_feasibility"

def load(name):
    return json.loads((ROOT / name).read_text())

def test_steamdeck_case_remains_unknown_not_repair_approved():
    result = assess_device_splice(load("steamdeck_oled_ssd.json"))
    assert result["overall_status"] == "unknown"
    assert result["checks"][0]["status"] == "compatible_on_paper"
    assert len([r for r in result["checks"] if r["status"] == "unknown"]) == 5
    assert not result["source_evidence_authentication_performed"]
    assert not result["power_on_authorized"]
    assert not result["release_authorized"]

def test_synthetic_controller_display_requires_validated_adapter():
    result = assess_device_splice(load("controller_display_demo.json"))
    assert result["overall_status"] == "adaptable_pending_validation"
    assert len(result["checks"]) == 8
    assert result["checks"][2]["adaptation_id"] == "buck_5_to_3v3"
    assert len(result["required_actions"]) == 1
    assert result["required_actions"][0]["interface_id"] == "display_power"
    assert not result["exact_mechanical_assembly_verified"]

def test_no_adapter_is_blocked():
    case = load("controller_display_demo.json")
    case["interfaces"][2].pop("adaptation")
    assert assess_device_splice(case)["overall_status"] == "blocked"

def test_infeasible_regulator_input_energy_is_blocked():
    case = load("controller_display_demo.json")
    case["interfaces"][2]["adaptation"]["input_current_required_a"] = 0.1
    result = assess_device_splice(case)
    assert result["checks"][2]["status"] == "blocked"
    assert result["overall_status"] == "blocked"

def test_shared_supply_rail_overload_is_blocked():
    case = load("controller_display_demo.json")
    case["interfaces"][0]["required"]["current_required_a"] = 1.9
    result = assess_device_splice(case)
    rail = next(row for row in result["checks"] if row["domain"] == "power_aggregate")
    assert rail["aggregate_required_a"] > rail["source_rating_a"]
    assert rail["status"] == "blocked"

def test_missing_adapter_input_budget_never_passes():
    case = load("controller_display_demo.json")
    case["interfaces"][2]["adaptation"].pop("input_current_required_a")
    result = assess_device_splice(case)
    assert result["overall_status"] == "blocked"
    assert any(row["domain"] == "power_aggregate" and row["status"] == "unknown" for row in result["checks"])

def test_large_component_colliding_with_lid_is_blocked():
    case = load("controller_display_demo.json")
    case["electromechanical_fit"].update({"status": "envelope_collision_detected", "blocker_count": 1})
    result = assess_device_splice(case)
    assert result["overall_status"] == "blocked"
    assert any(row["id"] == "physical_assembly_fit" and row["status"] == "blocked" for row in result["checks"])

def test_required_firmware_domain_must_not_be_omitted():
    case = load("controller_display_demo.json")
    case["interfaces"] = [r for r in case["interfaces"] if r["domain"] != "firmware"]
    result = assess_device_splice(case)
    assert result["overall_status"] == "unknown"
    assert any(row["id"] == "missing_domain:firmware" for row in result["checks"])

def test_missing_evidence_makes_interface_unknown():
    case = load("controller_display_demo.json")
    case["interfaces"][1]["evidence_refs"] = []
    assert assess_device_splice(case)["overall_status"] == "unknown"

@pytest.mark.parametrize("change", [
    lambda c: c["components"].append({"id": "controller"}),
    lambda c: c["interfaces"][0].update({"from": "missing_component"}),
    lambda c: c["interfaces"][1].update({"evidence_refs": ["made_up"]}),
    lambda c: c["interfaces"][0]["provided"].update({"current_max_a": float("nan")}),
    lambda c: c.update({"electromechanical_fit": {"schema": "wrong"}}),
])
def test_invalid_input_fails_closed(change):
    candidate = load("controller_display_demo.json")
    change(candidate)
    with pytest.raises(ValueError):
        assess_device_splice(candidate)

def test_missing_power_evidence_does_not_crash_shared_rail_accounting():
    case = load("controller_display_demo.json")
    case["interfaces"][0].pop("evidence_refs")
    case["interfaces"][2].pop("evidence_refs")
    report = assess_device_splice(case)
    assert report["overall_status"] == "unknown"
    assert not report["fabrication_authorized"]
