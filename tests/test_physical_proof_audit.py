from __future__ import annotations

from hardware_splicer.physical_proof_audit import audit_physical_proof


def _closed_voltage_gate(*, operator: str = "", method: str = "", value=5.0, unit: str = "V") -> dict:
    return {
        "gate_id": "supply_voltage",
        "gate_type": "voltage",
        "critical": True,
        "status": "closed",
        "measurement": {
            "value": value,
            "unit": unit,
            "operator": operator,
            "method": method,
        },
        "notes": [],
    }


def _real_capture(*, attestation: dict | None = None) -> dict:
    capture = {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "physical-proof-test",
        "operator_id": "bench_operator_01",
        "recorded_at": "2026-08-11T00:00:00+00:00",
        "simulated": False,
    }
    if attestation is not None:
        capture["operator_attestation"] = attestation
    return capture


def test_closed_status_without_measurement_provenance_cannot_defend_power_authority() -> None:
    session = {
        "power_on_authorized": True,
        "gates": [_closed_voltage_gate(operator="", method="")],
    }

    audit = audit_physical_proof(session)

    assert audit["status"] == "blocked"
    assert audit["bench_evidence_complete"] is False
    assert audit["independent_operator_proof"] is False
    assert audit["claim_ceiling"] == "software_or_incomplete_bench_evidence_only"
    codes = {row["code"] for row in audit["findings"]}
    assert "CRITICAL_GATE_EVIDENCE_INCOMPLETE" in codes
    assert "SESSION_AUTHORITY_EXCEEDS_EVIDENCE" in codes


def test_complete_real_bench_evidence_stops_below_independent_operator_claim() -> None:
    session = {
        "power_on_authorized": True,
        "gates": [_closed_voltage_gate(operator="bench_operator_01", method="calibrated_dmm")],
    }

    audit = audit_physical_proof(session, capture=_real_capture())

    assert audit["status"] == "pass"
    assert audit["bench_evidence_complete"] is True
    assert audit["independent_operator_proof"] is False
    assert audit["claim_ceiling"] == "bench_evidence_recorded"
    assert audit["checks"]["software_ci_is_physical_proof"] is False
    assert audit["checks"]["closed_status_alone_is_physical_proof"] is False


def test_independent_operator_claim_requires_explicit_attestation() -> None:
    session = {
        "power_on_authorized": True,
        "gates": [_closed_voltage_gate(operator="outsider_01", method="calibrated_dmm")],
    }
    capture = _real_capture(
        attestation={
            "operator_id": "outsider_01",
            "independent_of_design_authorship": True,
            "followed_published_procedure": True,
            "source_code_not_required": True,
            "procedure_id": "real-bench-operator-v1",
        }
    )
    capture["operator_id"] = "outsider_01"

    audit = audit_physical_proof(session, capture=capture)

    assert audit["status"] == "pass"
    assert audit["bench_evidence_complete"] is True
    assert audit["independent_operator_proof"] is True
    assert audit["claim_ceiling"] == "independent_operator_bench_evidence"
    assert audit["checks"]["operator_identity_real_world_verified"] is False


def test_simulated_capture_cannot_support_real_bench_claim() -> None:
    session = {
        "power_on_authorized": True,
        "gates": [_closed_voltage_gate(operator="bench_operator_01", method="calibrated_dmm")],
    }
    capture = _real_capture()
    capture["simulated"] = True

    audit = audit_physical_proof(session, capture=capture)

    assert audit["status"] == "blocked"
    assert audit["bench_evidence_complete"] is False
    assert audit["independent_operator_proof"] is False
    assert "BENCH_CAPTURE_SIMULATED" in {row["code"] for row in audit["findings"]}


def test_contract_edit_gate_requires_evidence_id_method_and_producer() -> None:
    weak = {
        "power_on_authorized": True,
        "gates": [
            {
                "gate_id": "interface_direction",
                "gate_type": "interface_contract_field",
                "requires_contract_edit": True,
                "critical": True,
                "status": "closed",
                "measurement": {
                    "contract_update": {
                        "evidence_id": "contract-evidence-01",
                    }
                },
            }
        ],
    }

    audit = audit_physical_proof(weak)
    assert audit["status"] == "blocked"
    finding = next(row for row in audit["findings"] if row["code"] == "CRITICAL_GATE_EVIDENCE_INCOMPLETE")
    assert set(finding["observed"]["missing"]) == {"method", "producer"}

    strong = {
        "power_on_authorized": True,
        "gates": [
            {
                "gate_id": "interface_direction",
                "gate_type": "interface_contract_field",
                "requires_contract_edit": True,
                "critical": True,
                "status": "closed",
                "measurement": {
                    "contract_update": {
                        "evidence_id": "contract-evidence-01",
                        "method": "protected_stimulus",
                        "producer": "operator_01+dmm_01",
                    }
                },
            }
        ],
    }
    passed = audit_physical_proof(strong)
    assert passed["status"] == "pass"
    assert passed["bench_evidence_complete"] is True
