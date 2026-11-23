"""Independent fixture regressions for declared, generic part substitutions.

These profiles are fictional digital test declarations, never inferred product
ratings or an inventory of hardware owned by the user.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.part_substitution import (
    SubstitutionSpecification,
    evaluate_substitution,
)


EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "part_substitution"


def example(name="cyberdeck-display-replacement.json"):
    return json.loads((EXAMPLES / name).read_text())


def evaluate(spec):
    # Exercise the typed public input, not a test-only compatibility shortcut.
    return evaluate_substitution(SubstitutionSpecification.model_validate(spec))


def normalized(spec):
    return SubstitutionSpecification.model_validate(spec).model_dump(mode="json", by_alias=True)


def original_part(spec, part_id):
    return next(row for row in spec["parts"] if row["part_id"] == part_id)


def revised_part(report, part_id):
    return next(row for row in report["revised"]["parts"] if row["part_id"] == part_id)


def port(part, port_id="dc"):
    return next(row for row in part["ports"] if row["port_id"] == port_id)


def checks(report, status=None):
    rows = report["checks"]
    return [row for row in rows if status is None or row["status"] == status]


def has_finding(report, text, status):
    return any(text in row["code"] for row in checks(report, status))


def hard_failures(report):
    return [row for row in checks(report, "fail") if not row["requires_adaptation"]]


def all_after_runtime_values(report):
    return [row["runtime_h"] for scenario in report["scenarios"]
            for row in scenario["after"]["runtime_by_source"]]


def test_declared_example_index_binds_exact_bytes_without_claiming_hardware():
    index = json.loads((EXAMPLES / "fixture-index.json").read_text())
    assert index["evidence_class"] == "declared_simulation_fixture"
    assert index["manufacturer_specification"] is False
    assert index["owned_inventory"] == []
    assert index["physical_validation_performed"] is False
    assert index["purchase_or_stock_claims"] is False
    for entry in index["examples"]:
        assert hashlib.sha256((EXAMPLES / entry["file"]).read_bytes()).hexdigest() == entry["sha256"]


@pytest.mark.parametrize("entry", json.loads((EXAMPLES / "fixture-index.json").read_text())["examples"],
                         ids=lambda entry: entry["file"])
def test_declared_examples_have_intact_bytes_and_expected_scope(entry):
    index = json.loads((EXAMPLES / "fixture-index.json").read_text())
    assert index["owned_inventory"] == []
    assert index["physical_validation_performed"] is False
    assert index["manufacturer_specification"] is False
    raw = (EXAMPLES / entry["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
    report = evaluate(json.loads(raw))
    assert report["status"] == entry["expected_status"]
    assert report["construction_ready"] is False
    assert report["physical_validation_performed"] is False
    assert report["complete_device_compatibility_verified"] is False
    assert report["manufacturing_approved"] is False
    assert report["source_bindings_verified"] is False
    if entry["expected_status"] != "unresolved":
        assert report["assessment_scope"]["basis"] == "declared_contract_checks_only"
        assert any(row["code"] == "signal_loading_timing_not_assessed" for row in report["unassessed"])


@pytest.mark.parametrize("filename", [
    "cyberdeck-display-replacement.json",
    "cyberdeck-controller-replacement.json",
    "cyberdeck-power-replacement.json",
])
def test_three_independent_variants_retain_assembly_identity_and_connections(filename):
    spec = example(filename)
    before = deepcopy(spec)
    canonical = normalized(spec)
    report = evaluate(spec)
    assert spec == before
    assert report["status"] == "requires_adaptation"
    assert report["revised"]["connections"] == canonical["connections"]
    changed = revised_part(report, spec["replace_part_id"])
    assert changed["replacement_profile_id"] == spec["candidate"]["part_id"]
    assert changed["position_mm"] == original_part(spec, spec["replace_part_id"])["position_mm"]
    assert changed["dimensions_mm"] == spec["candidate"]["dimensions_mm"]
    assert changed["mount"]["holes_mm"] == spec["candidate"]["mount"]["holes_mm"]
    assert {row["part_id"] for row in report["revised"]["parts"]} == {row["part_id"] for row in spec["parts"]}
    for source in canonical["parts"]:
        if source["part_id"] != spec["replace_part_id"]:
            retained = revised_part(report, source["part_id"])
            for field in ("name", "dimensions_mm", "position_mm", "mount", "ports"):
                assert retained[field] == source[field]
    assert report["required_adaptations"]


def test_voltage_range_overlap_is_insufficient_without_full_containment():
    spec = example()
    port(original_part(spec, "energy-store:alpha"))["voltage_range_v"] = [4.8, 5.2]
    port(spec["candidate"])["voltage_range_v"] = [5.0, 5.5]
    report = evaluate(spec)
    # [4.8,5.2] intersects [5.0,5.5], but part of the source range is unsafe.
    assert report["status"] == "blocked"
    assert has_finding(report, "voltage", "fail")


@pytest.mark.parametrize("missing_on", ["candidate", "unchanged_supply"])
def test_unknown_voltage_range_cannot_pass_declared_checks(missing_on):
    spec = example()
    part = spec["candidate"] if missing_on == "candidate" else original_part(spec, "energy-store:alpha")
    port(part)["voltage_range_v"] = None
    report = evaluate(spec)
    assert report["status"] == "unresolved"
    assert has_finding(report, "voltage", "unknown")


@pytest.mark.parametrize("missing_on", ["candidate", "unchanged_load", "unchanged_supply"])
def test_unknown_current_rating_never_becomes_a_success(missing_on):
    spec = example()
    part = {"candidate": spec["candidate"],
            "unchanged_load": original_part(spec, "input-pad#aux"),
            "unchanged_supply": original_part(spec, "energy-store:alpha")}[missing_on]
    port(part)["current_a"] = None
    if missing_on == "unchanged_supply":
        part["shared_output_limit_a"] = None
    report = evaluate(spec)
    assert report["status"] == "unresolved"
    assert has_finding(report, "current", "unknown")


def test_unrelated_unchanged_load_is_counted_in_whole_rail_capacity():
    spec = example()
    # The new panel is only 0.45 A. An unchanged 2.5 A keyboard makes the
    # assembly demand 1.1 + 0.45 + 2.5 = 4.05 A from the 3 A rail.
    port(original_part(spec, "input-pad#aux"))["current_a"] = 2.5
    report = evaluate(spec)
    assert report["status"] == "blocked"
    budget = next(row for row in checks(report, "fail")
                  if row["code"] == "power_current_budget" and row["scenario_id"] == "declared-normal")
    assert budget["demand_a"] == pytest.approx(4.05)
    assert budget["capacity_a"] == pytest.approx(3.0)
    assert budget["margin_a"] == pytest.approx(-1.05)
    assert "input-pad#aux" in budget["part_ids"]


def test_explicit_shared_supply_limit_also_constrains_a_single_output():
    spec = example()
    supply = original_part(spec, "energy-store:alpha")
    port(supply)["current_a"] = 4.0
    supply["shared_output_limit_a"] = 1.5
    report = evaluate(spec)
    # The 1.7 A normal assembly meets the port's 4 A rating while exceeding
    # the source part's explicitly declared 1.5 A overall current limit.
    assert report["status"] == "blocked"
    budget = next(row for row in checks(report, "fail")
                  if row["code"] == "shared_supply_budget" and row["scenario_id"] == "declared-normal")
    assert budget["demand_a"] == pytest.approx(1.7)
    assert budget["capacity_a"] == pytest.approx(1.5)
    assert all(value is None for value in all_after_runtime_values(report))


def test_declared_peak_scenario_cannot_hide_overload_behind_nominal_current():
    spec = example()
    spec["scenarios"] = [{"scenario_id": "unchanged-board-high-demand", "current_overrides": [
        {"part_id": "board@west.17", "port_id": "dc", "current_a": 2.6}]}]
    # 2.6 + 0.45 + 0.15 = 3.2 A despite the ordinary scenario's 1.7 A.
    report = evaluate(spec)
    assert report["status"] == "blocked"
    assert has_finding(report, "current", "fail")
    peak = next(row for row in report["scenarios"] if row["scenario_id"] == "unchanged-board-high-demand")
    assert peak["after"]["rails"][0]["current_a"] == pytest.approx(3.2)
    assert peak["after"]["rails"][0]["capacity_a"] == pytest.approx(3.0)


def test_same_connector_does_not_excuse_swapped_power_and_ground():
    spec = example()
    port(spec["candidate"])["pin_functions"] = {"1": "GND", "2": "V+"}
    report = evaluate(spec)
    assert report["status"] == "blocked"
    assert has_finding(report, "pin", "fail")
    assert all(value is None for value in all_after_runtime_values(report))


@pytest.mark.parametrize("change", [
    "missing_connector", "different_connector", "missing_pin_functions",
    "partial_pin_map", "nonbijective_pin_map", "different_port_kind", "missing_revised_port",
])
def test_incomplete_or_invalid_power_path_cannot_emit_device_runtime(change):
    spec = example()
    candidate_port = port(spec["candidate"])
    link = next(row for row in spec["connections"] if row["connection_id"] == "rail-to-panel/east.42")
    if change == "missing_connector":
        candidate_port["connector"] = None
    elif change == "different_connector":
        candidate_port["connector"] = "SIM-DIFFERENT-MATING-INTERFACE"
    elif change == "missing_pin_functions":
        candidate_port["pin_functions"] = None
    elif change == "partial_pin_map":
        link["pin_map"] = {"1": "1"}
    elif change == "nonbijective_pin_map":
        link["pin_map"] = {"1": "1", "2": "1"}
    elif change == "different_port_kind":
        candidate_port["kind"] = "signal"
    else:
        candidate_port["port_id"] = "new-port-without-a-graph-mapping"
    report = evaluate(spec)
    assert report["status"] in {"blocked", "unresolved"}
    assert all(row["after"]["total_power_w"] is None for row in report["scenarios"])
    assert all(value is None for value in all_after_runtime_values(report))


def test_current_override_cannot_erase_declared_base_demand_violation():
    spec = example()
    port(spec["candidate"])["current_a"] = 3.0
    spec["scenarios"] = [{"scenario_id": "operator-selected-low-current", "current_overrides": [
        {"part_id": spec["replace_part_id"], "port_id": "dc", "current_a": .1}]}]
    report = evaluate(spec)
    assert report["status"] == "blocked"
    # The low-current scenario is useful sensitivity data, but does not erase
    # the full declared 1.1 + 3.0 + 0.15 = 4.25 A assembly demand.
    assert any(row["code"] == "power_current_budget" and row["status"] == "fail"
               and row["demand_a"] == pytest.approx(4.25) for row in report["checks"])


def test_explicit_pin_mapping_expresses_repinning_without_losing_contact_ids():
    spec = example()
    port(spec["candidate"])["pin_functions"] = {"1": "GND", "2": "V+"}
    connection = next(row for row in spec["connections"] if row["connection_id"] == "rail-to-panel/east.42")
    connection["pin_map"] = {"1": "2", "2": "1"}
    report = evaluate(spec)
    assert report["status"] == "requires_adaptation"
    revised = next(row for row in report["revised"]["connections"] if row["connection_id"] == connection["connection_id"])
    assert revised["pin_map"] == {"1": "2", "2": "1"}
    assert not hard_failures(report)
    assert any(row["code"] == "repin_required" and row["requires_adaptation"] for row in checks(report, "fail"))


def test_pin_mapped_cable_does_not_convert_signal_protocol():
    spec = example()
    port(spec["candidate"], "picture")["protocol"] = "incompatible-fixture-raster-v9"
    picture = next(row for row in spec["connections"] if row["connection_id"] == "picture-link")
    picture["pin_map"] = {"A": "A", "B": "B", "C": "C"}
    report = evaluate(spec)
    assert report["status"] == "blocked"
    assert has_finding(report, "protocol", "fail")


def test_changed_hole_pattern_requires_adapter_even_when_body_fits():
    spec = example()
    source = original_part(spec, spec["replace_part_id"])
    assert spec["candidate"]["dimensions_mm"] != source["dimensions_mm"]
    assert spec["candidate"]["mount"]["holes_mm"] != source["mount"]["holes_mm"]
    report = evaluate(spec)
    assert report["status"] == "requires_adaptation"
    assert report["required_adaptations"]
    assert not hard_failures(report)
    assert any(row["code"] == "mount_pattern" and row["requires_adaptation"] for row in checks(report, "fail"))


def test_larger_body_cannot_pass_by_only_matching_electrical_ports():
    spec = example()
    spec["candidate"]["dimensions_mm"] = [300, 94, 10]
    report = evaluate(spec)
    assert report["status"] == "blocked"
    assert has_finding(report, "enclosure", "fail")


def test_candidate_collision_with_unrelated_retained_body_is_blocking():
    spec = example()
    spec["candidate"]["dimensions_mm"] = [160, 110, 10]
    # Panel at y=105 extends through 215; retained keyboard begins at y=200.
    report = evaluate(spec)
    assert report["status"] == "blocked"
    assert has_finding(report, "collision", "fail")


def test_source_identity_and_declared_pin_protocol_data_round_trip_untouched():
    spec = example("telemetry-sensor-replacement.json")
    source = {"source_id": "declared-fixture-source", "content_hash": "sha256:" + "a" * 64,
              "pointer": "/profiles/sensor:theta.99"}
    spec["candidate"]["source"] = source
    original_part(spec, "rail/42")["source"] = {
        "source_id": "retained-fixture-rail", "content_hash": "sha256:" + "b" * 64, "pointer": "/rail"}
    before = deepcopy(spec)
    report = evaluate(spec)
    assert spec == before
    assert report["status"] == "passes_declared_checks"
    assert revised_part(report, "node:south#7")["source"] == source
    assert revised_part(report, "rail/42")["source"] == original_part(spec, "rail/42")["source"]
    revised = revised_part(report, "node:south#7")
    assert revised["ports"] == normalized(spec)["candidate"]["ports"]
    assert revised["replacement_profile_id"] == "candidate:theta.99"


def test_unidentified_donor_remains_explicitly_unresolved():
    spec = example("unidentified-donor.json")
    report = evaluate(spec)
    assert report["status"] == "unresolved"
    assert checks(report, "unknown")
    revised = revised_part(report, spec["replace_part_id"])
    assert revised["dimensions_mm"] is None
    assert revised["manufacturer"] is None
    assert revised["mpn"] is None
    assert port(revised)["voltage_range_v"] is None
    assert port(revised)["pin_functions"] is None


def test_display_replacement_recomputes_power_and_runtime_from_all_retained_loads():
    report = evaluate(example())
    normal = next(row for row in report["scenarios"] if row["scenario_id"] == "declared-normal")
    assert normal["before"]["rails"][0]["current_a"] == pytest.approx(1.85)
    assert normal["after"]["rails"][0]["current_a"] == pytest.approx(1.7)
    assert normal["after"]["total_power_w"] == pytest.approx([4.9 * 1.7, 5.1 * 1.7])
    runtime = next(row for row in normal["after"]["runtime_by_source"] if row["part_id"] == "energy-store:alpha")
    assert runtime["runtime_h"] == pytest.approx([30 * .8 / (5.1 * 1.7), 30 * .8 / (4.9 * 1.7)])
    assert report["delta"]["dimensions_mm"] == [10, 4, -2]
    assert report["source_bindings_verified"] is False
    assert report["manufacturing_approved"] is False
    assert report["complete_device_compatibility_verified"] is False
    assert report["physical_authority_granted"] is False


@pytest.mark.parametrize("target", ["connection_part", "connection_port", "scenario_part", "scenario_port"])
def test_unknown_graph_or_scenario_identity_is_rejected_instead_of_ignored(target):
    spec = example()
    if target.startswith("connection"):
        field = "part_id" if target == "connection_part" else "port_id"
        spec["connections"][0]["to"][field] = "UNRESOLVED-CONTACT-999"
    else:
        field = "part_id" if target == "scenario_part" else "port_id"
        spec["scenarios"][1]["current_overrides"][0][field] = "UNRESOLVED-CONTACT-999"
    with pytest.raises(ValueError):
        evaluate(spec)
