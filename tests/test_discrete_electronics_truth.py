from __future__ import annotations

import copy
from pathlib import Path

from hardware_splicer.discrete_electronics_truth import (
    load_json_object,
    run_discrete_electronics_benchmark,
    validate_full_duplex_translator,
    validate_ldo_3v3,
    validate_selected_part_pin_identity,
)

_EVIDENCE = Path("experiments/electronics/discrete_uart_3v3_1v8_evidence.json")
_PROPOSAL = Path("experiments/electronics/discrete_uart_3v3_1v8_gpt56_sol.json")


def _data():
    return load_json_object(_PROPOSAL), load_json_object(_EVIDENCE)


def test_live_discrete_proposal_passes_datasheet_contracts_but_not_fabrication_closure() -> None:
    proposal, evidence = _data()
    report = run_discrete_electronics_benchmark(proposal, evidence)

    assert report["diagnostic_pass"] is True
    assert report["checks"]["exact_part_identity_grounded"] is True
    assert report["checks"]["selected_part_pin_names_grounded_in_datasheets"] is True
    assert report["checks"]["ldo_rail_and_stability_contracts_pass"] is True
    assert report["checks"]["full_duplex_translator_contract_pass"] is True
    assert report["checks"]["shared_direction_translator_rejected_for_full_duplex_uart"] is True
    assert report["checks"]["missing_ldo_output_capacitor_rejected"] is True
    assert report["checks"]["unresolved_footprints_block_fabrication_instead_of_being_guessed"] is True
    assert report["fabrication_ready"] is False
    assert report["power_on_ready"] is False
    assert report["fabrication_authorized"] is False


def test_hallucinated_pin_name_is_rejected_against_manufacturer_pin_table() -> None:
    proposal, evidence = _data()
    bad = copy.deepcopy(proposal)
    for net in bad["nets"]:
        if net["name"] == "HOST_TX_3V3":
            net["endpoints"] = ["J2.HOST_TX", "U2.A3"]
    result = validate_selected_part_pin_identity(bad, evidence)

    assert result["pass"] is False
    finding = next(row for row in result["findings"] if row["code"] == "UNKNOWN_DATASHEET_PIN")
    assert finding["ref"] == "U2"
    assert finding["pin"] == "A3"
    assert "A1" in finding["allowed_pins"]
    assert "A2" in finding["allowed_pins"]


def test_shared_dir_2t45_is_rejected_for_simultaneous_full_duplex_uart() -> None:
    proposal, evidence = _data()
    bad = copy.deepcopy(proposal)
    for row in bad["selected_parts"]:
        if row["ref"] == "U2":
            row["evidence_id"] = "part-sn74axc2t45dcur"
            row["mpn"] = "SN74AXC2T45DCUR"
    result = validate_full_duplex_translator(bad, evidence)

    assert result["pass"] is False
    assert any(row["code"] == "TRANSLATOR_DIRECTION_TOPOLOGY_INCOMPATIBLE" for row in result["findings"])


def test_wrong_direction_control_is_rejected_from_datasheet_function_table() -> None:
    proposal, evidence = _data()
    bad = copy.deepcopy(proposal)
    for net in bad["nets"]:
        if net["name"] == "+3V3":
            net["endpoints"] = [ep for ep in net["endpoints"] if ep != "U2.DIR1"]
        if net["name"] == "GND":
            net["endpoints"].append("U2.DIR1")
    result = validate_full_duplex_translator(bad, evidence)

    assert result["pass"] is False
    assert any(row["code"] == "TRANSLATOR_DIR1_WRONG" for row in result["findings"])


def test_missing_required_ldo_output_capacitor_is_rejected() -> None:
    proposal, evidence = _data()
    bad = copy.deepcopy(proposal)
    bad["passives"] = [row for row in bad["passives"] if row["ref"] != "C2"]
    for net in bad["nets"]:
        net["endpoints"] = [ep for ep in net["endpoints"] if not ep.startswith("C2.")]
    result = validate_ldo_3v3(bad, evidence)

    assert result["pass"] is False
    assert any(row["code"] == "LDO_OUTPUT_CAPACITOR_MISSING" for row in result["findings"])


def test_5v_is_rejected_on_axc_translator_supply() -> None:
    proposal, evidence = _data()
    bad = copy.deepcopy(proposal)
    bad["requirements"]["host_logic_v"] = 5.0
    result = validate_full_duplex_translator(bad, evidence)

    assert result["pass"] is False
    assert any(row["code"] == "TRANSLATOR_VCCA_OUT_OF_RANGE" for row in result["findings"])
