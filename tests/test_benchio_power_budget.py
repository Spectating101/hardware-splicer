from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "hardware" / "reference_designs" / "benchhmi_v0"
BUDGET_PATH = DESIGN / "benchio_power_budget_v0.json"
VALIDATOR_PATH = DESIGN / "validate_benchio_power_budget.py"

SPEC = importlib.util.spec_from_file_location("benchio_power_validator", VALIDATOR_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

BUDGET = json.loads(BUDGET_PATH.read_text())


def test_power_budget_closes_with_field_power_split() -> None:
    result = MODULE.validate(BUDGET)
    assert result["result"] == "PASS"
    assert result["host_usb_allocation_ma"] < 100
    assert result["field_logic_with_margin_ma"] < 1000
    assert result["field_logic_regulator_headroom_ma"] > 400


def test_old_2w_converter_is_explicitly_rejected() -> None:
    field = BUDGET["field_logic_5v"]
    old = field["rejected_previous_candidate"]
    assert old["capacity_ma"] == 400
    assert field["raw_worst_case_ma"] > old["capacity_ma"]
    assert old["decision"] == "REJECT"


def test_four_output_loads_are_not_charged_to_usb_or_logic_buck() -> None:
    loads = BUDGET["switched_field_loads"]
    assert loads["nominal_all_channels_ma"] == 1000
    assert loads["included_in_5v_field_logic_budget"] is False
    assert loads["included_in_usb_budget"] is False
    assert loads["preliminary_field_input_continuous_rating_a"] >= 2.0


def test_power_budget_cannot_open_physical_authority() -> None:
    authority = BUDGET["authority"]
    assert authority["power_architecture_budget_closed_for_schematic"] is True
    assert authority["exact_regulator_design_verified"] is False
    assert authority["fabrication_authorized"] is False
    assert authority["power_on_authorized"] is False
