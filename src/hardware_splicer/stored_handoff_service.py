"""Build deterministic fabrication handoff bundles from retained artifact ids."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .engineering_artifact_store import EngineeringArtifactStore
from .fabrication_handoff_bundle import FabricationHandoffBuilder, HandoffArtifact
from .fabrication_operator import FabricationValidationError


class StoredHandoffService:
    def __init__(self, *, artifacts: EngineeringArtifactStore) -> None:
        self.artifacts = artifacts
        self.builder = FabricationHandoffBuilder()

    def build(
        self,
        *,
        project_id: str,
        mission_id: str,
        revision_id: str,
        source_artifact_ids: Sequence[str],
        output_artifact_id: str,
        provenance: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        if isinstance(source_artifact_ids, (str, bytes, bytearray)) or not isinstance(source_artifact_ids, Sequence):
            raise FabricationValidationError("source_artifact_ids must be a list")
        if not source_artifact_ids or len(source_artifact_ids) > 256:
            raise FabricationValidationError("handoff requires 1..256 source artifacts")
        if len(source_artifact_ids) != len(set(source_artifact_ids)):
            raise FabricationValidationError("handoff source artifact ids must be unique")
        sources = []
        for artifact_id in source_artifact_ids:
            record = self.artifacts.describe(artifact_id)
            ext = _extension(record.media_type, record.kind)
            path = f"artifacts/{record.kind}/{record.artifact_id}{ext}"
            sources.append(HandoffArtifact(
                path=path,
                content=self.artifacts.bytes(record.artifact_id),
                role=record.kind,
                producer=record.producer,
                media_type=record.media_type,
                metadata={
                    "source_artifact_id": record.artifact_id,
                    "source_sha256": record.sha256,
                    "source_metadata": dict(record.metadata),
                },
            ))
        bundle = self.builder.build(
            project_id=project_id,
            mission_id=mission_id,
            revision_id=revision_id,
            artifacts=sources,
            provenance=provenance,
        )
        stored = self.artifacts.put(
            artifact_id=output_artifact_id,
            kind="handoff_bundle",
            content=bundle.zip_bytes,
            media_type="application/zip",
            producer="stored_handoff_service",
            metadata={
                "project_id": project_id,
                "mission_id": mission_id,
                "revision_id": revision_id,
                "source_artifact_ids": list(source_artifact_ids),
                "bundle_sha256": bundle.sha256,
                "manifest": dict(bundle.manifest),
            },
        )
        return {
            "schema": "hardware_splicer.stored_handoff_bundle.v1",
            "artifact": stored.public_dict(),
            "manifest": dict(bundle.manifest),
            "source_artifact_ids": list(source_artifact_ids),
            "physical_correctness": "UNPROVEN",
            "grants_physical_authority": False,
        }


def _extension(media_type: str, kind: str) -> str:
    mapping = {
        "application/zip": ".zip",
        "text/csv": ".csv",
        "application/json": ".json",
        "model/stl": ".stl",
        "model/3mf": ".3mf",
        "application/octet-stream": ".bin",
    }
    return mapping.get(media_type, f".{kind}")
