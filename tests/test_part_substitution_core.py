"""Additional evaluator edge cases; no native tools or filesystem mutations."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from hardware_splicer.part_substitution import SubstitutionSpecification, evaluate_substitution


EXAMPLES = Path(__file__).resolve().parents[1] / "examples/part_substitution"


def spec():
    return json.loads((EXAMPLES / "telemetry-sensor-replacement.json").read_text())


def codes(report, status):
    return {row["code"] for row in report["checks"] if row["status"] == status}


def test_revised_assembly_is_valid_input_for_second_arbitrary_replacement():
    initial = spec()
    report = evaluate_substitution(initial)
    followup = {**initial, "parts": report["revised"]["parts"], "connections": report["revised"]["connections"]}
    followup["replace_part_id"] = "logger@west.9"
    followup["candidate"] = deepcopy(next(row for row in followup["parts"] if row["part_id"] == "logger@west.9"))
    followup["candidate"]["part_id"] = "next-device/921"
    followup["candidate"]["mpn"] = "another-explicit-specification"
    second = evaluate_substitution(SubstitutionSpecification.model_validate(followup))
    assert second["status"] == "passes_declared_checks"
    assert next(row for row in second["revised"]["parts"] if row["part_id"] == "node:south#7")["replacement_profile_id"] == "candidate:theta.99"
    assert next(row for row in second["revised"]["parts"] if row["part_id"] == "logger@west.9")["replacement_profile_id"] == "next-device/921"


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), "3.3"])
def test_nonfinite_boolean_or_coerced_numeric_claims_are_rejected(bad):
    value = spec()
    value["candidate"]["ports"][0]["current_a"] = bad
    with pytest.raises(ValueError):
        evaluate_substitution(value)


def test_bidirectional_interval_is_checked_in_both_directions():
    value = spec()
    value["candidate"]["ports"][1]["direction"] = "bidirectional"
    value["parts"][2]["ports"][1]["direction"] = "bidirectional"
    report = evaluate_substitution(value)
    # 0..3.3 fits 0..3.6, but reverse operation exceeds the first endpoint.
    assert report["status"] == "blocked"
    assert "signal_voltage_containment" in codes(report, "fail")
    assert any(row["code"] == "bidirectional_signal_behaviour_not_assessed" for row in report["unassessed"])


def test_missing_bidirectional_voltage_stays_unknown_not_unassessed():
    value = spec()
    value["candidate"]["ports"][1].update(direction="bidirectional", voltage_range_v=None)
    value["parts"][2]["ports"][1]["direction"] = "bidirectional"
    report = evaluate_substitution(value)
    assert report["status"] == "unresolved"
    assert "signal_voltage_unknown" in codes(report, "unknown")


def test_changed_power_negotiation_protocol_is_not_a_plain_connector_match():
    value = spec()
    value["parts"][0]["ports"][0]["protocol"] = "declared-protocol-A"
    value["candidate"]["ports"][0]["protocol"] = "declared-protocol-B"
    report = evaluate_substitution(value)
    assert report["status"] == "blocked"
    assert "protocol_mismatch" in codes(report, "fail")
    assert all(row["after"]["total_power_w"] is None for row in report["scenarios"])


def test_missing_replacement_port_cannot_create_fake_power_savings():
    value = spec()
    value["candidate"]["ports"] = [value["candidate"]["ports"][1]]
    report = evaluate_substitution(value)
    assert report["status"] == "unresolved"
    assert "replacement_port_missing" in codes(report, "unknown")
    assert all(row["power_delta_w"] is None for row in report["scenarios"])


def test_unconnected_optional_load_override_is_reported_not_dropped():
    value = spec()
    part = value["parts"][2]
    port = {**part["ports"][0], "port_id": "optional-aux", "required": False}
    part["ports"].append(port)
    value["scenarios"] = [{"scenario_id": "aux-active", "current_overrides": [
        {"part_id": part["part_id"], "port_id": "optional-aux", "current_a": 1.0}]}]
    report = evaluate_substitution(value)
    assert report["status"] == "unresolved"
    assert "scenario_input_unconnected" in codes(report, "unknown")
    assert next(row for row in report["scenarios"] if row["scenario_id"] == "aux-active")["after"]["total_power_w"] is None


def test_nominal_mount_coordinates_outside_body_are_a_conflict():
    value = spec()
    value["candidate"]["mount"]["holes_mm"][0] = [900, 900]
    report = evaluate_substitution(value)
    assert report["status"] == "blocked"
    assert "mount_nominal_bounds" in codes(report, "fail")


def test_signal_timing_exclusion_never_becomes_complete_device_approval():
    report = evaluate_substitution(spec())
    assert report["status"] == "passes_declared_checks"
    assert report["direct_replacement_within_declared_scope"] is True
    assert report["unassessed"]
    assert report["assessment_scope"]["basis"] == "declared_contract_checks_only"
    assert report["complete_device_compatibility_verified"] is False
    assert report["construction_ready"] is False


@pytest.mark.parametrize("limit_field,scope", [("port", "source_rail"), ("shared", "shared_source")])
def test_power_budget_adaptation_states_actual_required_capacity_without_selecting_hardware(limit_field, scope):
    value = spec()
    source = value["parts"][0]
    if limit_field == "port":
        source["ports"][0]["current_a"] = .4
    else:
        source["shared_output_limit_a"] = .4
    report = evaluate_substitution(value)
    adaptation = next(row for row in report["required_adaptations"]
                      if row["kind"] == "power_budget" and row["scenario_id"] == "declared" and row["budget_scope"] == scope)
    assert report["status"] == "blocked"
    assert adaptation["required_capacity_a"] == pytest.approx(.08 + .35)
    assert adaptation["demand_a"] == pytest.approx(.43)
    assert adaptation["declared_capacity_a"] == .4
    assert adaptation["current_margin_a"] == pytest.approx(-.03)
    assert adaptation["required_evidence"]
    assert adaptation["hardware_selected"] is False
    assert adaptation["automatically_applied"] is False


def test_voltage_adaptation_preserves_permitted_interval_and_known_load_demand():
    value = spec()
    value["candidate"]["ports"][0]["voltage_range_v"] = [5.0, 5.5]
    report = evaluate_substitution(value)
    adaptation = next(row for row in report["required_adaptations"]
                      if row["kind"] == "regulated_power_path" and row["scenario_id"] == "declared")
    assert report["status"] == "blocked"
    assert adaptation["source_voltage_range_v"] == [4.9, 5.1]
    assert adaptation["permitted_voltage_range_v"] == [5.0, 5.5]
    assert adaptation["required_output_current_a"] == .08
    assert adaptation["source_port"] == {"part_id": "rail/42", "port_id": "dc"}
    assert adaptation["load_port"] == {"part_id": "node:south#7", "port_id": "dc"}
    assert adaptation["hardware_selected"] is False
    assert adaptation["automatically_applied"] is False
