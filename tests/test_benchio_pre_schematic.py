from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "hardware" / "reference_designs" / "benchhmi_v0"
ARCH = json.loads((DESIGN / "benchio_architecture_v0.json").read_text())
CONTRACT = json.loads((DESIGN / "benchio_schematic_contract.json").read_text())


def test_benchio_is_donor_independent_at_the_electrical_boundary() -> None:
    assert ARCH["architecture_decision"] == "STANDALONE_SIDECAR_DECOUPLED_FROM_DONOR_INTERNALS"
    assert CONTRACT["design_boundary"]["donor_interface"] == "USB 2.0 external only"
    assert CONTRACT["design_boundary"]["donor_internal_signals_used"] is False
    assert CONTRACT["design_boundary"]["donor_internal_power_used"] is False
    assert CONTRACT["authority"]["schematic_design_authorized"] is True
    assert CONTRACT["authority"]["pcb_design_authorized"] is False


def test_benchio_keeps_field_and_host_domains_explicit() -> None:
    assert ARCH["field_isolation"]["host_to_field_isolation_target_vdc"] >= 1500
    assert ARCH["field_isolation"]["channel_to_channel_isolation_claim"] is False
    assert ARCH["interfaces"]["can"]["host_isolated"] is True
    assert all(row["host_isolated"] for row in ARCH["interfaces"]["rs485"])
    assert ARCH["interfaces"]["digital_inputs"]["channels"] == 4
    assert ARCH["interfaces"]["digital_outputs"]["channels"] == 4
    invariants = "\n".join(CONTRACT["topology_invariants"])
    assert "must not be copper-connected" in invariants
    assert "No donor-internal rail" in invariants


def test_benchio_default_state_is_safe_and_physical_authority_stays_closed() -> None:
    safe = "\n".join(CONTRACT["default_safe_state"])
    assert "digital outputs commanded OFF" in safe
    assert "field logic power disabled" in safe
    assert CONTRACT["authority"]["fabrication_authorized"] is False
    assert CONTRACT["authority"]["power_on_authorized"] is False
    assert CONTRACT["authority"]["physical_correctness"] == "UNPROVEN"


def test_benchio_screening_bom_fits_revised_small_batch_parts_budget() -> None:
    with (DESIGN / "BENCHIO_BOM_SCREENING.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    total = next(row for row in rows if row["part_or_group"] == "SCREENING_BOM")
    assert float(total["screening_ext_twd_10up"]) <= 1500
    assert float(total["screening_unit_twd_1up"]) > float(total["screening_ext_twd_10up"])
