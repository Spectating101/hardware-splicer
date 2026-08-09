from __future__ import annotations

from pathlib import Path

from hardware_splicer.electronics_foundation_benchmark import (
    load_electronics_bundle,
    run_electronics_foundation_benchmark,
    strict_signal_voltage_audit,
    translated_hcsr04_contract_audit,
    validate_catalog_identity_and_pins,
)
from hardware_splicer.netlist import CircuitNetlist, run_erc

_BUNDLE = Path("experiments/electronics/esp32_hcsr04_level_shift_gpt56_sol.json")


def _bundle() -> dict:
    return load_electronics_bundle(_BUNDLE)


def test_translated_design_is_catalog_grounded_and_strictly_separates_logic_domains() -> None:
    netlist = CircuitNetlist.from_dict(_bundle()["translated_design"])
    identity = validate_catalog_identity_and_pins(netlist)
    hs_erc = run_erc(netlist)
    strict = strict_signal_voltage_audit(netlist)
    topology = translated_hcsr04_contract_audit(netlist)

    assert identity["pass"] is True
    assert hs_erc["pass"] is True
    assert strict["pass"] is True
    assert topology["pass"] is True
    assert topology["translator_internal_electrical_behavior_verified"] is False


def test_unsafe_direct_logic_domains_are_rejected_by_both_erc_and_independent_oracle() -> None:
    netlist = CircuitNetlist.from_dict(_bundle()["unsafe_direct_design"])
    hs_erc = run_erc(netlist)
    strict = strict_signal_voltage_audit(netlist)

    assert hs_erc["pass"] is False
    mismatch_errors = [
        row for row in hs_erc["violations"]
        if row["rule"] == "erc-voltage-mismatch" and row["severity"] == "error"
    ]
    assert len(mismatch_errors) >= 2
    assert strict["pass"] is False
    finding = next(row for row in strict["findings"] if row["net"] == "ECHO_DIRECT")
    assert finding["fixed_voltages_v"] == [3.3, 5.0]


def test_electronics_foundation_benchmark_records_successful_referee_repair_replay() -> None:
    report = run_electronics_foundation_benchmark(_bundle())

    assert report["diagnostic_pass"] is True
    assert report["design_ready"] is False
    assert report["fabrication_ready"] is False
    assert report["power_on_ready"] is False
    assert report["checks"]["translated_design_passes_hs_erc"] is True
    assert report["checks"]["translated_design_passes_independent_strict_signal_audit"] is True
    assert report["checks"]["unsafe_direct_5v_to_3v3_is_rejected_by_strict_oracle"] is True
    assert report["checks"]["repaired_hs_erc_rejects_unsafe_direct_logic_domains"] is True
    assert report["repair_replay"]["classification"] == "TOOL_IMPLEMENTATION_REPAIRED"
    assert report["fabrication_authorized"] is False
    assert report["power_on_authorized"] is False
