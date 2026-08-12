from __future__ import annotations

from hardware_splicer.bench_capture_bridge import build_bench_capture_template_from_gates
from hardware_splicer.physical_proof_audit import audit_physical_proof


def _closed_voltage_session() -> dict:
    return {
        "power_on_authorized": True,
        "gates": [
            {
                "gate_id": "supply_voltage",
                "gate_type": "voltage",
                "critical": True,
                "status": "closed",
                "measurement": {
                    "value": 5.0,
                    "unit": "V",
                    "operator": "bench_operator_01",
                    "method": "calibrated_dmm",
                },
                "notes": [],
            }
        ],
    }


def test_capture_without_explicit_simulation_status_cannot_count_as_real_bench_evidence() -> None:
    capture = {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "missing-simulation-declaration",
        "operator_id": "bench_operator_01",
        "recorded_at": "2026-08-12T00:00:00+00:00",
    }

    audit = audit_physical_proof(_closed_voltage_session(), capture=capture)

    assert audit["status"] == "blocked"
    assert audit["capture_simulated"] is None
    assert audit["bench_evidence_complete"] is False
    assert audit["independent_operator_proof"] is False
    assert audit["claim_ceiling"] == "software_or_incomplete_bench_evidence_only"
    assert "BENCH_CAPTURE_SIMULATION_STATUS_MISSING" in {
        row["code"] for row in audit["findings"]
    }


def test_generated_bench_capture_template_requires_explicit_simulation_declaration() -> None:
    template = build_bench_capture_template_from_gates([])

    assert "simulated" in template
    assert template["simulated"] is None
