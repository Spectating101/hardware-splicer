from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

QUALIFIER_PATH = ROOT / "experiments" / "product_factory" / "qualify_pf002_donor.py"
Q_SPEC = importlib.util.spec_from_file_location("pf002_qualifier_test", QUALIFIER_PATH)
Q = importlib.util.module_from_spec(Q_SPEC)
assert Q_SPEC.loader is not None
Q_SPEC.loader.exec_module(Q)

ADVANCE_PATH = ROOT / "experiments" / "product_factory" / "advance_pf002.py"
A_SPEC = importlib.util.spec_from_file_location("pf002_advance_test", ADVANCE_PATH)
A = importlib.util.module_from_spec(A_SPEC)
assert A_SPEC.loader is not None
A_SPEC.loader.exec_module(A)

SIM = json.loads(
    (ROOT / "experiments" / "product_factory" / "fixtures" / "benchhmi_pos462_simulated_pass.json").read_text()
)
TEMPLATE = json.loads(
    (ROOT / "experiments" / "product_factory" / "fixtures" / "benchhmi_pos462_real_template.json").read_text()
)


def _unit_test_real_pass() -> dict:
    record = json.loads(json.dumps(SIM))
    record["record_id"] = "UNIT-TEST-REAL-SHAPE"
    record["simulated"] = False
    record["donor"]["serial_or_asset_id"] = "UNIT-TEST-SERIAL"
    for row in record["checks"].values():
        row["evidence"] = "unit-test concrete evidence placeholder"
    return record


def test_perfect_simulation_still_cannot_qualify_real_donor() -> None:
    result = Q.evaluate(SIM)
    assert result["physical_checks_pass"] is True
    assert result["decision"] == "SIMULATION_ONLY_NOT_ACCEPTED"
    assert result["real_donor_accepted"] is False
    assert "real_physical_state_not_explicit" in result["blockers"]
    assert result["authority"]["benchio_design_gate_may_open"] is False


def test_empty_real_template_holds_fail_closed() -> None:
    result = Q.evaluate(TEMPLATE)
    assert result["decision"] == "HOLD_OR_REJECT_DONOR"
    assert result["real_donor_accepted"] is False
    assert "motherboard_not_b91" in result["blockers"]
    assert "donor_identity_missing" in result["blockers"]


def test_unit_level_real_shape_can_open_only_schematic_engineering() -> None:
    status = A.project_status(_unit_test_real_pass())
    assert status["state"] == "REAL_DONOR_ACCEPTED_BENCHIO_DESIGN_MAY_START"
    assert status["authority"]["benchio_schematic_design_authorized"] is True
    assert status["authority"]["pcb_design_authorized"] is False
    assert status["authority"]["fabrication_authorized"] is False
    assert status["authority"]["power_on_authorized"] is False
    assert status["authority"]["sale_authorized"] is False


def test_simulation_rehearses_pipeline_without_opening_design() -> None:
    status = A.project_status(SIM)
    assert status["state"] == "SIMULATION_REHEARSAL_COMPLETE_REAL_DONOR_REQUIRED"
    assert status["projected_stages"]["DESIGN_SCHEMATIC"] == "BLOCKED_ON_REAL_DONOR_ACCEPTANCE"
    assert status["authority"]["benchio_schematic_design_authorized"] is False


def test_mains_repair_rejects_even_otherwise_passing_record() -> None:
    record = _unit_test_real_pass()
    record["requires_mains_side_repair"] = True
    result = Q.evaluate(record)
    assert result["real_donor_accepted"] is False
    assert "mains_side_repair_required" in result["blockers"]
