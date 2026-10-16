"""Model-derived visual inspection claims over retained camera observations.

A vision model may help identify likely defects, markings, orientation or assembly
state, but its output is not a physical measurement and cannot directly pass or
fail a validation procedure. This module binds every inference to the exact raw
observation hash and retains the result as a non-executable inspection artifact.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .engineering_artifact_store import EngineeringArtifactStore
from .fabrication_operator import FabricationValidationError
from .physical_observation_store import PhysicalObservationStore


class VisionInferenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisionClaim:
    label: str
    confidence: float
    description: str
    region: tuple[float, float, float, float] | None = None

    def validate(self) -> None:
        _text(self.label, "claim label", 128)
        _text(self.description, "claim description", 1000)
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool) or not 0 <= float(self.confidence) <= 1:
            raise FabricationValidationError("vision claim confidence must be between 0 and 1")
        if self.region is not None:
            if len(self.region) != 4:
                raise FabricationValidationError("vision claim region must contain x1,y1,x2,y2")
            values = [float(value) for value in self.region]
            if any(value < 0 or value > 1 for value in values) or values[0] > values[2] or values[1] > values[3]:
                raise FabricationValidationError("vision claim region must be normalized 0..1 bounds")


class VisionInferenceProvider(Protocol):
    model_id: str
    model_version: str

    def infer(self, *, image: bytes, media_type: str, task_id: str) -> Sequence[VisionClaim | Mapping[str, Any]]: ...


class VisionInspectionService:
    def __init__(
        self,
        *,
        observations: PhysicalObservationStore,
        artifacts: EngineeringArtifactStore,
        provider: VisionInferenceProvider,
    ) -> None:
        self.observations = observations
        self.artifacts = artifacts
        self.provider = provider
        self.model_id = _id(provider.model_id, "vision model_id")
        self.model_version = _id(provider.model_version, "vision model_version")

    def inspect(
        self,
        *,
        observation_id: str,
        task_id: str,
        output_artifact_id: str,
    ) -> dict[str, Any]:
        task = _id(task_id, "vision task_id")
        observation = self.observations.describe(observation_id)
        if observation.kind != "image":
            raise FabricationValidationError("vision inspection requires an image observation")
        image = self.observations.read_bytes(observation_id)
        if hashlib.sha256(image).hexdigest() != observation.sha256:
            raise FabricationValidationError("vision input no longer matches retained observation hash")
        try:
            raw_claims = self.provider.infer(image=image, media_type=observation.media_type, task_id=task)
        except Exception as exc:
            if isinstance(exc, (FabricationValidationError, VisionInferenceError)):
                raise
            raise VisionInferenceError("vision inference provider failed") from exc
        if isinstance(raw_claims, (str, bytes, bytearray)) or not isinstance(raw_claims, Sequence):
            raise VisionInferenceError("vision provider must return a claim sequence")
        if len(raw_claims) > 256:
            raise VisionInferenceError("vision provider returned too many claims")
        claims = [_claim(value) for value in raw_claims]
        result = {
            "schema": "hardware_splicer.visual_inspection_inference.v1",
            "observation_id": observation.observation_id,
            "observation_sha256": observation.sha256,
            "observation_media_type": observation.media_type,
            "task_id": task,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "claims": claims,
            "claim_count": len(claims),
            "evidence_class": "model_inference",
            "hypothesis_only": True,
            "may_auto_promote_to_physical_evidence": False,
            "passes_validation": None,
            "physical_correctness": "UNPROVEN",
            "grants_physical_authority": False,
        }
        encoded = (json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        stored = self.artifacts.put(
            artifact_id=output_artifact_id,
            kind="inspection_document",
            content=encoded,
            media_type="application/json",
            producer="vision_inspection",
            metadata={
                "observation_id": observation.observation_id,
                "observation_sha256": observation.sha256,
                "task_id": task,
                "model_id": self.model_id,
                "model_version": self.model_version,
                "inference_sha256": hashlib.sha256(encoded).hexdigest(),
            },
        )
        return {
            "schema": "hardware_splicer.stored_visual_inspection.v1",
            "inspection": result,
            "artifact": stored.public_dict(),
            "physical_correctness": "UNPROVEN",
        }


def _claim(value: VisionClaim | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, VisionClaim):
        claim = value
    elif isinstance(value, Mapping):
        try:
            raw_region = value.get("region")
            region = tuple(raw_region) if raw_region is not None else None
            claim = VisionClaim(
                label=value.get("label"),
                confidence=value.get("confidence"),
                description=value.get("description"),
                region=region,  # type: ignore[arg-type]
            )
        except (TypeError, ValueError) as exc:
            raise VisionInferenceError("vision claim is malformed") from exc
    else:
        raise VisionInferenceError("vision claim must be an object")
    claim.validate()
    return {
        "label": claim.label.strip(),
        "confidence": float(claim.confidence),
        "description": claim.description.strip(),
        "region": list(claim.region) if claim.region is not None else None,
    }


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or any(ord(ch) < 32 and ch not in "\t\n" for ch in cleaned):
        raise FabricationValidationError(f"{field} must be bounded text")
    return cleaned
