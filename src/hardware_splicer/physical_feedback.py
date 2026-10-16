"""Explicit promotion from raw physical observations to engineering evidence.

Capture is not proof.  This module connects the new immutable observation store
(camera frames, serial logs, instrument traces, telemetry) to Hardware Splicer's
existing calibrated physical-evidence model without collapsing those two stages.

Only a caller that supplies a concrete procedure, target, acceptance criteria and
pass/fail disposition can create a ``PhysicalEvidenceRecord``.  Instrument-backed
records remain subject to the existing calibration requirements in that model.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from .fabrication_operator import FabricationValidationError
from .machine_project import AuthorityState
from .physical_evidence import (
    FindingLink,
    PhysicalEvidenceKind,
    PhysicalEvidenceRecord,
)
from .physical_observation_store import PhysicalObservationStore


def _text(value: Any, *, field: str, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or any(ord(ch) < 32 for ch in cleaned):
        raise FabricationValidationError(f"{field} must be bounded printable text")
    return cleaned


def _strings(value: Iterable[str], *, field: str, maximum: int = 50) -> list[str]:
    if isinstance(value, (str, bytes)):
        raise FabricationValidationError(f"{field} must be a list of strings")
    rows = list(value)
    if not rows or len(rows) > maximum:
        raise FabricationValidationError(f"{field} must contain 1 to {maximum} entries")
    return [_text(item, field=f"{field} item", maximum=256) for item in rows]


def _json_object(value: Mapping[str, Any] | None, *, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise FabricationValidationError(f"{field} must be an object")
    try:
        encoded = json.dumps(dict(value), sort_keys=True, ensure_ascii=False, allow_nan=False)
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError(f"{field} must be canonical JSON") from exc


def promote_observation_to_evidence(
    observations: PhysicalObservationStore,
    observation_id: str,
    *,
    evidence_id: str,
    project_id: str,
    candidate_revision: str,
    kind: PhysicalEvidenceKind | str,
    target_ids: Iterable[str],
    procedure_id: str,
    passed: bool,
    operator: str,
    acceptance_criteria: Mapping[str, Any],
    measured_values: Mapping[str, Any] | None = None,
    instrument_ids: Iterable[str] = (),
    calibration_ids: Iterable[str] = (),
    artifact_hashes: Mapping[str, str] | None = None,
    environment: Mapping[str, Any] | None = None,
    fixture_state: Mapping[str, Any] | None = None,
    interlock_state: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    finding_links: Iterable[FindingLink | Mapping[str, Any]] | None = None,
) -> PhysicalEvidenceRecord:
    """Promote one retained observation into measured evidence under explicit criteria.

    This does not grant fabrication, flash, power, motion or release authority.  It
    only constructs the existing evidence record after re-reading and re-hashing the
    retained raw bytes.  Authorization remains a separate higher-level assessment.
    """

    if not isinstance(observations, PhysicalObservationStore):
        raise FabricationValidationError("promotion requires a PhysicalObservationStore")
    record = observations.describe(observation_id)
    # describe() re-reads the payload and rejects a hash/size mismatch.
    observations.read_bytes(observation_id)

    if isinstance(kind, str):
        try:
            evidence_kind = PhysicalEvidenceKind(kind)
        except ValueError as exc:
            raise FabricationValidationError("unsupported physical evidence kind") from exc
    elif isinstance(kind, PhysicalEvidenceKind):
        evidence_kind = kind
    else:
        raise FabricationValidationError("kind must be a PhysicalEvidenceKind")
    if type(passed) is not bool:
        raise FabricationValidationError("passed must be a boolean")

    instruments = list(instrument_ids)
    calibrations = list(calibration_ids)
    if instruments:
        instruments = _strings(instruments, field="instrument_ids")
        if not calibrations:
            raise FabricationValidationError(
                "instrument-backed observation promotion requires calibration_ids"
            )
        calibrations = _strings(calibrations, field="calibration_ids")
    elif calibrations:
        raise FabricationValidationError("calibration_ids require instrument_ids")

    extra_metadata = _json_object(metadata, field="metadata")
    # The promotion boundary owns these fields; callers cannot rewrite provenance.
    for reserved in (
        "simulated",
        "source_class",
        "observation_id",
        "observation_sha256",
        "observation_source_id",
        "observation_media_type",
    ):
        if reserved in extra_metadata:
            raise FabricationValidationError(f"metadata.{reserved} is reserved by the promotion boundary")
    promoted_metadata = {
        **extra_metadata,
        "simulated": False,
        "source_class": "machine_observation",
        "observation_id": record.observation_id,
        "observation_sha256": record.sha256,
        "observation_source_id": record.source_id,
        "observation_media_type": record.media_type,
    }

    links = None
    if finding_links is not None:
        links = [
            item if isinstance(item, FindingLink) else FindingLink.model_validate(item)
            for item in finding_links
        ]

    return PhysicalEvidenceRecord(
        evidence_id=_text(evidence_id, field="evidence_id"),
        project_id=_text(project_id, field="project_id"),
        candidate_revision=_text(candidate_revision, field="candidate_revision"),
        kind=evidence_kind,
        target_ids=_strings(target_ids, field="target_ids"),
        procedure_id=_text(procedure_id, field="procedure_id"),
        passed=passed,
        captured_at=record.captured_at,
        operator=_text(operator, field="operator"),
        measured_values=_json_object(measured_values, field="measured_values"),
        acceptance_criteria=_json_object(acceptance_criteria, field="acceptance_criteria"),
        instrument_ids=instruments,
        calibration_ids=calibrations,
        artifact_hashes=_json_object(artifact_hashes, field="artifact_hashes"),
        environment=_json_object(environment, field="environment"),
        fixture_state=_json_object(fixture_state, field="fixture_state"),
        interlock_state=_json_object(interlock_state, field="interlock_state"),
        raw_refs=[f"physical-observation:{record.observation_id}:sha256:{record.sha256}"],
        authority=AuthorityState.MEASURED,
        metadata=promoted_metadata,
        finding_links=links,
    )
