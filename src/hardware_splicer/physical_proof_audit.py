"""Deterministic evidence audit for physical and independent-operator proof claims.

This module does not perform a bench test and never opens physical authority. It recomputes
what claims the persisted evidence can defend, independently of a session's own readiness
flags. Software/CI success, a closed-gate status, and an independent outsider run are three
different claims and must remain distinguishable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


SCHEMA_VERSION = "hardware_splicer.physical_proof_audit.v1"
SESSION_FILE = "SPLICE_BENCH_SESSION.json"
_NUMERIC_GATE_TYPES = {
    "voltage",
    "current",
    "interface_measurement",
    "psu_ramp",
}


def _rows(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _finding(code: str, path: str, message: str, *, observed: Any = None) -> Dict[str, Any]:
    return {
        "code": code,
        "path": path,
        "message": message,
        "observed": observed,
        "severity": "blocking",
    }


def _nonempty(value: Any) -> bool:
    return bool(str(value or "").strip())


def _numeric_gate_expected(gate: Mapping[str, Any]) -> bool:
    gate_type = str(gate.get("gate_type") or "").strip().lower()
    if gate_type in _NUMERIC_GATE_TYPES:
        return True
    if gate_type != "measurement":
        return False
    prompt = str(gate.get("prompt") or "").lower()
    return any(token in prompt for token in ("voltage", "current", "rail", "vmotor"))


def _contract_update_evidence(measurement: Mapping[str, Any]) -> tuple[bool, list[str]]:
    update = measurement.get("contract_update")
    if not isinstance(update, Mapping):
        return False, ["contract_update"]
    missing = [
        key
        for key in ("evidence_id", "method", "producer")
        if not _nonempty(update.get(key))
    ]
    return not missing, missing


def _measurement_evidence(gate: Mapping[str, Any]) -> tuple[bool, list[str]]:
    measurement = gate.get("measurement")
    if not isinstance(measurement, Mapping):
        return False, ["measurement"]

    if gate.get("requires_contract_edit") or str(gate.get("gate_type") or "") == "interface_contract_field":
        return _contract_update_evidence(measurement)

    missing: list[str] = []
    if not _nonempty(measurement.get("operator")):
        missing.append("operator")
    if not _nonempty(measurement.get("method")):
        missing.append("method")

    value = measurement.get("value")
    notes = gate.get("notes")
    has_notes = any(_nonempty(row) for row in notes) if isinstance(notes, list) else _nonempty(notes)
    if value is None and not has_notes:
        missing.append("observation")

    if _numeric_gate_expected(gate):
        if value is None or (isinstance(value, str) and not value.strip()):
            if "observation" not in missing:
                missing.append("value")
        if not _nonempty(measurement.get("unit")):
            missing.append("unit")

    return not missing, missing


def audit_physical_proof(
    bench_session: Mapping[str, Any] | None,
    *,
    capture: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Recompute the defensible physical-evidence claim ceiling.

    ``independent_operator_proof`` requires an explicit attestation in the capture. The
    audit cannot verify a person's real-world identity; it only checks that the claim is
    represented explicitly and separately from developer-authored bench evidence.
    """

    session = dict(bench_session or {})
    capture_body = dict(capture or {})
    gates = _rows(session.get("gates"))
    findings: list[Dict[str, Any]] = []

    critical = [row for row in gates if bool(row.get("critical"))]
    closed_critical = [row for row in critical if str(row.get("status") or "") == "closed"]
    open_critical = [row for row in critical if str(row.get("status") or "") != "closed"]

    for index, gate in enumerate(open_critical):
        findings.append(
            _finding(
                "CRITICAL_BENCH_GATE_OPEN",
                f"bench.gates[{index}]",
                "Critical physical-evidence gate is not closed.",
                observed=gate.get("gate_id"),
            )
        )

    evidence_complete_count = 0
    for gate in closed_critical:
        ok, missing = _measurement_evidence(gate)
        if ok:
            evidence_complete_count += 1
            continue
        findings.append(
            _finding(
                "CRITICAL_GATE_EVIDENCE_INCOMPLETE",
                f"bench.gates.{gate.get('gate_id') or 'unknown'}.measurement",
                "Closed critical gate lacks the provenance/observation needed to defend a physical proof claim.",
                observed={"missing": missing, "gate_type": gate.get("gate_type")},
            )
        )

    capture_present = bool(capture_body)
    capture_simulated = bool(capture_body.get("simulated")) if capture_present else None
    capture_operator = str(capture_body.get("operator_id") or "").strip()
    capture_recorded_at = str(capture_body.get("recorded_at") or "").strip()
    if capture_present and capture_simulated:
        findings.append(
            _finding(
                "BENCH_CAPTURE_SIMULATED",
                "capture.simulated",
                "Simulated capture cannot support a real physical proof claim.",
                observed=True,
            )
        )
    if capture_present and not capture_operator:
        findings.append(
            _finding(
                "BENCH_CAPTURE_OPERATOR_MISSING",
                "capture.operator_id",
                "Physical capture does not identify the recording operator.",
            )
        )
    if capture_present and not capture_recorded_at:
        findings.append(
            _finding(
                "BENCH_CAPTURE_TIME_MISSING",
                "capture.recorded_at",
                "Physical capture does not record when the observations were made.",
            )
        )

    attestation = capture_body.get("operator_attestation")
    attestation_map = dict(attestation) if isinstance(attestation, Mapping) else {}
    independence_fields = {
        "operator_id": str(attestation_map.get("operator_id") or capture_operator).strip(),
        "independent_of_design_authorship": attestation_map.get("independent_of_design_authorship") is True,
        "followed_published_procedure": attestation_map.get("followed_published_procedure") is True,
        "source_code_not_required": attestation_map.get("source_code_not_required") is True,
        "procedure_id": str(attestation_map.get("procedure_id") or "").strip(),
    }
    independent_attestation_complete = bool(
        independence_fields["operator_id"]
        and independence_fields["independent_of_design_authorship"]
        and independence_fields["followed_published_procedure"]
        and independence_fields["source_code_not_required"]
        and independence_fields["procedure_id"]
    )

    bench_evidence_complete = bool(
        critical
        and not open_critical
        and evidence_complete_count == len(closed_critical)
        and (not capture_present or (capture_simulated is False and capture_operator and capture_recorded_at))
    )
    independent_operator_proof = bool(bench_evidence_complete and independent_attestation_complete)

    if independent_operator_proof:
        claim_ceiling = "independent_operator_bench_evidence"
    elif bench_evidence_complete:
        claim_ceiling = "bench_evidence_recorded"
    else:
        claim_ceiling = "software_or_incomplete_bench_evidence_only"

    session_claims_power = session.get("power_on_authorized") is True
    if session_claims_power and not bench_evidence_complete:
        findings.append(
            _finding(
                "SESSION_AUTHORITY_EXCEEDS_EVIDENCE",
                "bench.power_on_authorized",
                "Bench session claims power-on authority beyond the evidence this audit can defend.",
                observed=True,
            )
        )

    blocking = [row for row in findings if row.get("severity") == "blocking"]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked" if blocking else "pass",
        "claim_ceiling": claim_ceiling,
        "bench_evidence_complete": bench_evidence_complete,
        "independent_operator_proof": independent_operator_proof,
        "critical_gate_count": len(critical),
        "closed_critical_gate_count": len(closed_critical),
        "critical_gate_evidence_complete_count": evidence_complete_count,
        "capture_present": capture_present,
        "capture_simulated": capture_simulated,
        "independent_attestation": independence_fields,
        "finding_count": len(findings),
        "blocking_finding_count": len(blocking),
        "findings": findings,
        "checks": {
            "software_ci_is_physical_proof": False,
            "closed_status_alone_is_physical_proof": False,
            "operator_identity_real_world_verified": False,
            "independent_operator_claim_requires_explicit_attestation": True,
        },
        "authority_effect": "none",
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def audit_physical_proof_build(
    build_dir: str | Path,
    *,
    capture_path: str | Path | None = None,
) -> Dict[str, Any]:
    """Load persisted bench/capture evidence and audit its defensible claim ceiling."""
    root = Path(build_dir).resolve()
    session_path = root / SESSION_FILE
    if not session_path.is_file():
        raise FileNotFoundError(f"bench session not found: {session_path}")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    if not isinstance(session, Mapping):
        raise ValueError(f"bench session must be a JSON object: {session_path}")

    capture: Dict[str, Any] = {}
    resolved_capture_path: Path | None = None
    if capture_path is not None:
        resolved_capture_path = Path(capture_path).resolve()
        if not resolved_capture_path.is_file():
            raise FileNotFoundError(f"bench capture not found: {resolved_capture_path}")
        loaded = json.loads(resolved_capture_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"bench capture must be a JSON object: {resolved_capture_path}")
        capture = loaded

    report = audit_physical_proof(session, capture=capture)
    return {
        **report,
        "build_dir": str(root),
        "bench_session_path": str(session_path),
        "capture_path": str(resolved_capture_path) if resolved_capture_path else None,
    }
