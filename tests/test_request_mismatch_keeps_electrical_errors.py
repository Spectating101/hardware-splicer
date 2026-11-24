"""A missing requested part must not hide an electrical error: both are blockers, in the gate and in
the compact verdict."""

from __future__ import annotations

from hardware_splicer.build_verdict import agent_verdict
from hardware_splicer.design_quality import build_design_quality_gate

MISMATCH = {
    "status": "mismatch",
    "missing_parts": [{"module_id": "sg90", "names": ["pan"], "requested": 2, "in_design": 1}],
}
QUALITY = {
    "build_graph_compiled": True,
    "electrical_safety_pass": False,
    "drc_pass": True,
    "electrical_issues": [{"level": "error", "message": "2 devices would all answer at 0x77.", "code": "i2c_address_clash"}],
}


def test_the_gate_lists_the_missing_part_and_the_electrical_error() -> None:
    gate = build_design_quality_gate(QUALITY, request_fidelity=MISMATCH)

    assert any("requested part sg90" in b for b in gate["blockers"])
    assert "2 devices would all answer at 0x77." in gate["blockers"]


def test_the_compact_verdict_lists_both() -> None:
    gate = build_design_quality_gate(QUALITY, request_fidelity=MISMATCH)
    verdict = agent_verdict({"ok": False, "design_quality_gate": gate})

    assert any("requested part sg90" in b for b in verdict["blockers"])
    assert "2 devices would all answer at 0x77." in verdict["blockers"]
