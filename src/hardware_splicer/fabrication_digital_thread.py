"""Hash-linked fabrication digital thread.

This provenance graph connects requirements/revisions to EDA, mechanical,
firmware, CAM, physical execution and observation artifacts without treating
provenance as engineering truth. Every artifact stays UNPROVEN here; physical
measurement/authorization lives in the dedicated evidence and authority models.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .fabrication_operator import FabricationValidationError


@dataclass(frozen=True)
class ThreadArtifact:
    artifact_id: str
    kind: str
    sha256: str
    size_bytes: int | None
    producer: str
    metadata: Mapping[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "producer": self.producer,
            "metadata": _canonical(dict(self.metadata)),
            "physical_correctness": "UNPROVEN",
        }


class FabricationDigitalThread:
    def __init__(self, *, project_id: str, mission_id: str, revision_id: str) -> None:
        self.project_id = _id(project_id, "project_id")
        self.mission_id = _id(mission_id, "mission_id")
        self.revision_id = _id(revision_id, "revision_id")
        self._artifacts: dict[str, ThreadArtifact] = {}
        self._activities: list[dict[str, Any]] = []
        self._activity_ids: set[str] = set()

    def add_artifact(
        self,
        *,
        artifact_id: str,
        kind: str,
        sha256: str,
        producer: str,
        size_bytes: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        aid = _id(artifact_id, "artifact_id")
        if aid in self._artifacts:
            raise FabricationValidationError("digital-thread artifact id already exists")
        digest = _sha(sha256, "artifact sha256")
        producer_id = _id(producer, "producer")
        kind_id = _id(kind, "artifact kind")
        if size_bytes is not None and (type(size_bytes) is not int or size_bytes < 0):
            raise FabricationValidationError("artifact size_bytes must be a non-negative integer")
        artifact = ThreadArtifact(
            aid,
            kind_id,
            digest,
            size_bytes,
            producer_id,
            _canonical(dict(metadata or {})),
        )
        self._artifacts[aid] = artifact
        return artifact.public_dict()

    def record_activity(
        self,
        *,
        activity_id: str,
        activity_type: str,
        actor: str,
        inputs: Sequence[str],
        outputs: Sequence[str],
        receipt: Mapping[str, Any],
        evidence_class: str,
    ) -> dict[str, Any]:
        event_id = _id(activity_id, "activity_id")
        if event_id in self._activity_ids:
            raise FabricationValidationError("digital-thread activity id already exists")
        if isinstance(inputs, (str, bytes)) or isinstance(outputs, (str, bytes)):
            raise FabricationValidationError("activity inputs/outputs must be lists")
        in_ids = [_id(value, "input artifact") for value in inputs]
        out_ids = [_id(value, "output artifact") for value in outputs]
        if not out_ids:
            raise FabricationValidationError("digital-thread activity requires at least one output")
        missing = sorted(set(in_ids + out_ids).difference(self._artifacts))
        if missing:
            raise FabricationValidationError("activity references unknown artifacts: " + ", ".join(missing))
        if len(in_ids) != len(set(in_ids)) or len(out_ids) != len(set(out_ids)):
            raise FabricationValidationError("activity artifact references must be unique")
        if evidence_class not in {
            "model",
            "deterministic_tool",
            "physical_dispatch",
            "raw_observation",
            "promoted_physical_evidence",
            "human_decision",
        }:
            raise FabricationValidationError("unsupported digital-thread evidence class")
        canonical_receipt = _canonical(dict(receipt))
        previous_hash = self._activities[-1]["event_sha256"] if self._activities else None
        event = {
            "schema": "hardware_splicer.fabrication_thread_activity.v1",
            "sequence": len(self._activities) + 1,
            "activity_id": event_id,
            "activity_type": _id(activity_type, "activity_type"),
            "actor": _id(actor, "actor"),
            "inputs": in_ids,
            "outputs": out_ids,
            "evidence_class": evidence_class,
            "receipt_sha256": _canonical_sha(canonical_receipt),
            "receipt": canonical_receipt,
            "previous_event_sha256": previous_hash,
            "grants_authority": False,
            "physical_correctness": "UNPROVEN",
        }
        event["event_sha256"] = _canonical_sha(event)
        self._activities.append(event)
        self._activity_ids.add(event_id)
        return _canonical(event)

    def manifest(self) -> dict[str, Any]:
        value = {
            "schema": "hardware_splicer.fabrication_digital_thread.v1",
            "project_id": self.project_id,
            "mission_id": self.mission_id,
            "revision_id": self.revision_id,
            "artifacts": [self._artifacts[key].public_dict() for key in sorted(self._artifacts)],
            "activities": _canonical(self._activities),
            "head_event_sha256": self._activities[-1]["event_sha256"] if self._activities else None,
            "physical_correctness": "UNPROVEN",
            "grants_physical_authority": False,
        }
        value["thread_sha256"] = _canonical_sha(value)
        return value

    def trace_artifact(self, artifact_id: str) -> dict[str, Any]:
        aid = _id(artifact_id, "artifact_id")
        if aid not in self._artifacts:
            raise FabricationValidationError("unknown digital-thread artifact")
        producing = [event for event in self._activities if aid in event["outputs"]]
        consuming = [event for event in self._activities if aid in event["inputs"]]
        return {
            "artifact": self._artifacts[aid].public_dict(),
            "produced_by": _canonical(producing),
            "consumed_by": _canonical(consuming),
            "physical_correctness": "UNPROVEN",
        }


def _canonical(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("digital-thread value must be canonical JSON") from exc


def _canonical_sha(value: Any) -> str:
    encoded = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise FabricationValidationError(f"{field} must be SHA-256")
    try:
        int(value, 16)
    except ValueError as exc:
        raise FabricationValidationError(f"{field} must be SHA-256") from exc
    return value.lower()


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
