"""Strict projection of bench_topology_capture.v1 packets into machine evidence.

Rows are never matched by fuzzy prose. A measurement must either carry an exact
known engineering-object identifier or be assigned through an explicit target map.
The complete capture is canonicalized and SHA-256 pinned into every evidence record.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Mapping

from .bench_capture_bridge import collect_capture_measurements, extract_bench_capture
from .machine_evidence import record_evidence_and_promote
from .machine_project import AuthorityState, MachineProject


class BenchCaptureEvidenceError(ValueError):
    pass


_PASS = {"pass", "passed", "ok", "verified", "measured", "normal", "closed"}
_VALID_CALIBRATION = {"valid", "current", "calibrated", "in_calibration"}
_AUTHORITY_ORDER = {
    AuthorityState.UNKNOWN.value: 0,
    AuthorityState.PROPOSED.value: 1,
    AuthorityState.DECLARED.value: 2,
    AuthorityState.OBSERVED.value: 3,
    AuthorityState.MEASURED.value: 4,
    AuthorityState.VERIFIED.value: 5,
    AuthorityState.AUTHORIZED.value: 6,
}
_TARGET_COLLECTIONS = (
    ("requirements", "requirement_id"),
    ("subsystems", "subsystem_id"),
    ("components", "component_id"),
    ("interfaces", "interface_id"),
    ("constraints", "constraint_id"),
    ("artifacts", "artifact_id"),
)


def _canonical_digest(capture: Mapping[str, Any]) -> str:
    payload = json.dumps(capture, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _slug(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "")).strip("-") or "row"


def _object_index(project: MachineProject) -> Dict[str, tuple[str, Dict[str, Any]]]:
    body = project.model_dump(mode="json")
    index: Dict[str, tuple[str, Dict[str, Any]]] = {}
    for collection, id_field in _TARGET_COLLECTIONS:
        for row in body.get(collection, []):
            index[str(row.get(id_field))] = (collection, row)
    return index


def _explicit_target(
    measurement: Mapping[str, Any],
    target_map: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str] | None:
    keys = [
        measurement.get("measurement_id"),
        measurement.get("gate_id"),
        measurement.get("interface_id"),
        measurement.get("block_id"),
        measurement.get("board_id"),
    ]
    for raw in keys:
        key = str(raw or "")
        mapped = target_map.get(key)
        if mapped:
            collection = str(mapped.get("collection") or "")
            object_id = str(mapped.get("object_id") or "")
            if not collection or not object_id:
                raise BenchCaptureEvidenceError(
                    f"target map entry {key!r} requires collection and object_id"
                )
            return collection, object_id
    return None


def _exact_target(
    measurement: Mapping[str, Any],
    index: Mapping[str, tuple[str, Dict[str, Any]]],
) -> tuple[str, str] | None:
    for field in ("interface_id", "component_id", "subsystem_id", "requirement_id", "artifact_id"):
        object_id = str(measurement.get(field) or "")
        if object_id and object_id in index:
            collection, _ = index[object_id]
            return collection, object_id
    return None


def _instrument_index(capture: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return {
        str(row.get("instrument_id")): row
        for row in capture.get("instruments") or []
        if isinstance(row, Mapping) and row.get("instrument_id")
    }


def _evidence_authority(
    capture: Mapping[str, Any],
    measurement: Mapping[str, Any],
    instruments: Mapping[str, Mapping[str, Any]],
) -> tuple[AuthorityState, bool, list[str]]:
    warnings: list[str] = []
    simulated = bool(capture.get("simulated") or measurement.get("simulated"))
    instrument_id = str(measurement.get("instrument_id") or "")
    instrument = instruments.get(instrument_id) if instrument_id else None
    calibration = str((instrument or {}).get("calibration_status") or "").strip().lower()
    if calibration == "simulated":
        simulated = True
    if simulated:
        return AuthorityState.OBSERVED, True, warnings
    if instrument is None:
        warnings.append("measurement has no matching instrument record; authority limited to observed")
        return AuthorityState.OBSERVED, False, warnings
    if calibration not in _VALID_CALIBRATION:
        warnings.append(
            f"instrument {instrument_id!r} calibration status {calibration or 'missing'!r}; authority limited to observed"
        )
        return AuthorityState.OBSERVED, False, warnings
    return AuthorityState.MEASURED, False, warnings


def project_bench_capture_to_evidence(
    project: MachineProject,
    packet: Mapping[str, Any],
    *,
    target_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Return a candidate machine project plus deterministic capture provenance."""

    capture = extract_bench_capture(packet)
    if not capture:
        raise BenchCaptureEvidenceError("expected bench_topology_capture.v1 packet")
    capture_id = str(capture.get("capture_id") or "").strip()
    if not capture_id:
        raise BenchCaptureEvidenceError("bench capture requires capture_id")
    rows = collect_capture_measurements(capture)
    if not rows:
        raise BenchCaptureEvidenceError("bench capture contains no measurement rows")

    index = _object_index(project)
    explicit_map = target_map or {}
    instruments = _instrument_index(capture)
    digest = _canonical_digest(capture)
    candidate = project
    evidence_ids: list[str] = []
    promotions: list[Dict[str, Any]] = []
    warnings: list[Dict[str, Any]] = []

    for position, measurement in enumerate(rows, start=1):
        status = str(measurement.get("status") or measurement.get("result") or "pass").strip().lower()
        measurement_key = str(
            measurement.get("measurement_id")
            or measurement.get("gate_id")
            or f"row-{position}"
        )
        if status not in _PASS:
            warnings.append(
                {
                    "code": "measurement_not_passed",
                    "measurement": measurement_key,
                    "message": f"measurement status {status!r} was not imported as supporting evidence",
                }
            )
            continue

        target = _explicit_target(measurement, explicit_map) or _exact_target(measurement, index)
        if target is None:
            warnings.append(
                {
                    "code": "measurement_target_unresolved",
                    "measurement": measurement_key,
                    "message": "measurement requires an exact object identifier or explicit target map",
                }
            )
            continue
        collection, object_id = target
        indexed = index.get(object_id)
        if indexed is None or indexed[0] != collection:
            raise BenchCaptureEvidenceError(
                f"measurement {measurement_key!r} maps to unknown target {collection}/{object_id}"
            )

        authority, simulated, row_warnings = _evidence_authority(capture, measurement, instruments)
        for message in row_warnings:
            warnings.append(
                {
                    "code": "measurement_authority_limited",
                    "measurement": measurement_key,
                    "message": message,
                }
            )
        evidence_id = f"bench-{_slug(capture_id)}-{_slug(measurement_key)}"
        evidence = {
            "evidence_id": evidence_id,
            "kind": f"bench_{measurement.get('kind') or measurement.get('type') or 'measurement'}",
            "basis": "simulation" if simulated else ("instrument" if authority == AuthorityState.MEASURED else "observation"),
            "ref": measurement.get("artifact_uri") or capture.get("capture_ref") or f"bench-capture:{capture_id}",
            "supports": [object_id],
            "authority": authority.value,
            "simulated": simulated,
            "metadata": {
                "capture_id": capture_id,
                "capture_sha256": digest,
                "recorded_at": capture.get("recorded_at"),
                "operator_id": measurement.get("operator_id") or capture.get("operator_id"),
                "instrument_id": measurement.get("instrument_id"),
                "measurement": dict(measurement),
            },
        }

        current = str(indexed[1].get("authority") or AuthorityState.UNKNOWN.value)
        requested = authority.value
        row_promotions: list[Dict[str, Any]] = []
        if not simulated and _AUTHORITY_ORDER[requested] > _AUTHORITY_ORDER.get(current, 0):
            row_promotions.append(
                {
                    "collection": collection,
                    "object_id": object_id,
                    "authority": requested,
                }
            )
            promotions.extend(row_promotions)
        candidate = record_evidence_and_promote(
            candidate,
            evidence=evidence,
            promotions=row_promotions,
        )
        evidence_ids.append(evidence_id)

    if not evidence_ids:
        raise BenchCaptureEvidenceError(
            "bench capture produced no canonical evidence; inspect unresolved target and status warnings"
        )

    return {
        "project": candidate,
        "capture_id": capture_id,
        "capture_sha256": digest,
        "evidence_ids": evidence_ids,
        "promotions": promotions,
        "warnings": warnings,
        "measurement_count": len(rows),
        "imported_count": len(evidence_ids),
    }
