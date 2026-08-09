from __future__ import annotations

import copy
from pathlib import Path

from hardware_splicer.discrete_capacitance_truth import audit_ldo_capacitance_evidence
from hardware_splicer.discrete_electronics_truth import load_json_object

_EVIDENCE = Path("experiments/electronics/discrete_uart_3v3_1v8_evidence.json")
_PROPOSAL = Path("experiments/electronics/discrete_uart_3v3_1v8_gpt56_sol.json")


def _data():
    return load_json_object(_PROPOSAL), load_json_object(_EVIDENCE)


def test_generic_1uf_x7r_caps_meet_nominal_requirement_but_do_not_close_effective_capacitance() -> None:
    proposal, evidence = _data()
    result = audit_ldo_capacitance_evidence(proposal, evidence)
    assert result["status"] == "blocked"
    assert result["nominal_requirement_pass"] is True
    assert result["effective_capacitance_closed"] is False
    assert len(result["unresolved"]) == 2
    assert {row["role"] for row in result["rows"]} == {"ldo_input", "ldo_output"}
    assert all(row["status"] == "unresolved" for row in result["rows"])


def test_nominal_cap_below_datasheet_minimum_is_hard_failure() -> None:
    proposal, evidence = _data()
    bad = copy.deepcopy(proposal)
    for row in bad["passives"]:
        if row["ref"] == "C2":
            row["value_uf"] = 0.1
    result = audit_ldo_capacitance_evidence(bad, evidence)
    assert result["status"] == "failed"
    assert any(row["code"] == "NOMINAL_CAPACITANCE_BELOW_DATASHEET_MINIMUM" for row in result["hard_failures"])


def test_effective_capacitance_can_close_only_with_persisted_identity_and_at_bias_value() -> None:
    proposal, evidence = _data()
    closed = copy.deepcopy(proposal)
    for row in closed["passives"]:
        if row["ref"] in {"C1", "C2"}:
            row["mpn"] = f"evidence-cap-{row['ref']}"
            row["effective_capacitance_uf_at_operating_bias"] = 0.7
    result = audit_ldo_capacitance_evidence(closed, evidence)
    assert result["status"] == "closed"
    assert result["effective_capacitance_closed"] is True
    assert not result["hard_failures"]
    assert not result["unresolved"]


def test_claimed_effective_value_below_datasheet_minimum_fails() -> None:
    proposal, evidence = _data()
    bad = copy.deepcopy(proposal)
    for row in bad["passives"]:
        if row["ref"] in {"C1", "C2"}:
            row["mpn"] = f"evidence-cap-{row['ref']}"
            row["effective_capacitance_uf_at_operating_bias"] = 0.3
    result = audit_ldo_capacitance_evidence(bad, evidence)
    assert result["status"] == "failed"
    assert sum(row["code"] == "EFFECTIVE_CAPACITANCE_BELOW_STABILITY_MINIMUM" for row in result["hard_failures"]) == 2
