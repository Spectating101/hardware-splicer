"""A design the quality gate blocks never carries the "build_ready" readiness label."""

from hardware_splicer.design_quality import build_design_quality_gate

CLEAN = {"drc_pass": True, "electrical_safety_pass": True, "electrical_errors": 0, "electrical_warnings": 0,
         "build_graph_compiled": True, "build_ready": True, "circuit_readiness": "build_ready"}


def test_clean_design_reads_build_ready():
    gate = build_design_quality_gate(dict(CLEAN))
    assert gate["build_ready"] is True and gate["circuit_readiness"] == "build_ready"


def test_request_mismatch_blocks_and_drops_the_ready_label():
    mismatch = {"status": "mismatch", "missing_parts": [
        {"module_id": "sg90", "names": ["servo"], "requested": 2, "in_design": 1}]}
    gate = build_design_quality_gate(dict(CLEAN), request_fidelity=mismatch)
    assert gate["build_ready"] is False
    assert gate["circuit_readiness"] != "build_ready"
