"""Server-owned executable artifacts for physical operators.

Physical operators act on immutable generated artifacts, never on raw commands
supplied at dispatch time.  A printer consumes G-code, a CNC/laser consumes a
machine-job/toolpath artifact, a programmer consumes firmware, and a robot
consumes a motion-plan artifact.  The registry keeps bytes private and exposes
only stable ids, hashes and bounded metadata to the agent layer.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from .fabrication_operator import FabricationValidationError
from .physical_operator import PhysicalExecutionPlan, PhysicalOperatorRegistry

_ARTIFACT_KINDS = frozenset({"gcode", "machine_job", "firmware", "motion_plan", "measurement_recipe"})
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_COMPATIBILITY = {
    ("printer", "start"): frozenset({"gcode"}),
    ("printer", "resume"): frozenset({"gcode"}),
    ("cnc", "start"): frozenset({"machine_job"}),
    ("cnc", "resume"): frozenset({"machine_job"}),
    ("laser", "start"): frozenset({"machine_job"}),
    ("laser", "resume"): frozenset({"machine_job"}),
    ("programmer", "flash"): frozenset({"firmware"}),
    ("robot", "execute_motion"): frozenset({"motion_plan"}),
    ("robot", "resume_motion"): frozenset({"motion_plan"}),
}


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value.strip()):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return value.strip()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise FabricationValidationError("artifact metadata must be an object")
    try:
        return json.loads(json.dumps(dict(value), sort_keys=True, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("artifact metadata must be JSON serializable") from exc


@dataclass(frozen=True)
class PhysicalArtifact:
    artifact_id: str
    kind: str
    sha256: str
    size_bytes: int
    generator: str
    generator_receipt_sha256: str | None
    metadata: Mapping[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema": "hardware_splicer.physical_artifact.v1",
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "generator": self.generator,
            "generator_receipt_sha256": self.generator_receipt_sha256,
            "metadata": json.loads(json.dumps(dict(self.metadata))),
        }


class PhysicalArtifactRegistry:
    def __init__(self) -> None:
        self._records: dict[str, tuple[PhysicalArtifact, bytes]] = {}

    def register(
        self,
        *,
        artifact_id: str,
        kind: str,
        content: bytes | bytearray,
        generator: str,
        generator_receipt_sha256: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> PhysicalArtifact:
        key = _id(artifact_id, "artifact_id")
        kind = _id(kind, "artifact kind")
        if kind not in _ARTIFACT_KINDS:
            raise FabricationValidationError("unsupported physical artifact kind")
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise FabricationValidationError("physical artifact content must be non-empty bytes")
        data = bytes(content)
        generator = _id(generator, "generator")
        if generator_receipt_sha256 is not None:
            if not isinstance(generator_receipt_sha256, str) or len(generator_receipt_sha256) != 64:
                raise FabricationValidationError("generator receipt hash must be SHA-256")
            try:
                int(generator_receipt_sha256, 16)
            except ValueError as exc:
                raise FabricationValidationError("generator receipt hash must be SHA-256") from exc
            generator_receipt_sha256 = generator_receipt_sha256.lower()
        if key in self._records:
            raise FabricationValidationError(f"duplicate physical artifact {key!r}")
        record = PhysicalArtifact(
            artifact_id=key,
            kind=kind,
            sha256=_sha256(data),
            size_bytes=len(data),
            generator=generator,
            generator_receipt_sha256=generator_receipt_sha256,
            metadata=_canonical_metadata(metadata),
        )
        self._records[key] = (record, data)
        return record

    def describe(self, artifact_id: str) -> dict[str, Any]:
        return self._record(artifact_id).public_dict()

    def list_public(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        if kind is not None and kind not in _ARTIFACT_KINDS:
            raise FabricationValidationError("unsupported physical artifact kind")
        records = [record.public_dict() for record, _data in self._records.values() if kind is None or record.kind == kind]
        return sorted(records, key=lambda item: item["artifact_id"])

    def bytes(self, artifact_id: str) -> bytes:
        key = _id(artifact_id, "artifact_id")
        try:
            return bytes(self._records[key][1])
        except KeyError as exc:
            raise FabricationValidationError(f"unknown physical artifact {key!r}") from exc

    def build_actuation_plan(
        self,
        *,
        operators: PhysicalOperatorRegistry,
        operator_id: str,
        project_id: str,
        mission_id: str,
        action: str,
        artifact_id: str,
        bindings: Mapping[str, Any] | None = None,
    ) -> PhysicalExecutionPlan:
        descriptor = operators.descriptor(operator_id)
        action_desc = descriptor.action(action)
        if action_desc.action_class != "actuate":
            raise FabricationValidationError("artifact actuation plans require an actuate action")
        artifact = self._record(artifact_id)
        allowed = _COMPATIBILITY.get((descriptor.kind, action))
        if allowed is None or artifact.kind not in allowed:
            raise FabricationValidationError(
                f"artifact kind {artifact.kind!r} is not valid for {descriptor.kind}.{action}"
            )
        payload = {
            "artifact_id": artifact.artifact_id,
            "artifact_kind": artifact.kind,
            "artifact_sha256": artifact.sha256,
            "generator": artifact.generator,
            "generator_receipt_sha256": artifact.generator_receipt_sha256,
            "bindings": _canonical_metadata(bindings),
        }
        return operators.plan(
            operator_id=operator_id,
            project_id=project_id,
            mission_id=mission_id,
            action=action,
            payload=payload,
        )

    def verify_plan_artifact(self, plan: PhysicalExecutionPlan) -> PhysicalArtifact:
        if not isinstance(plan.payload, Mapping):
            raise FabricationValidationError("physical execution plan payload is invalid")
        artifact_id = plan.payload.get("artifact_id")
        artifact = self._record(artifact_id)
        if plan.payload.get("artifact_kind") != artifact.kind or plan.payload.get("artifact_sha256") != artifact.sha256:
            raise FabricationValidationError("physical execution plan artifact binding is stale or tampered")
        return artifact

    def _record(self, artifact_id: Any) -> PhysicalArtifact:
        key = _id(artifact_id, "artifact_id")
        try:
            return self._records[key][0]
        except KeyError as exc:
            raise FabricationValidationError(f"unknown physical artifact {key!r}") from exc
