"""Mechanical CAD -> slicer -> registered G-code pipeline.

The agent selects only server-registered geometry and slicer profile ids. HS
renders the existing OpenSCAD source, slices the resulting immutable geometry,
and registers the exact G-code bytes in the physical artifact registry. Raw
geometry/profile/G-code bytes never need to cross the agent-facing boundary.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .fabrication_operator import FabricationValidationError
from .openscad_operator import OpenScadOperator
from .physical_artifact import PhysicalArtifactRegistry
from .slicer_operator import SlicerOperator
from .slicer_registry import SlicerProfileRegistry


class MechanicalFabricationPipeline:
    def __init__(
        self,
        *,
        cad: OpenScadOperator,
        slicer: SlicerOperator,
        profiles: SlicerProfileRegistry,
        artifacts: PhysicalArtifactRegistry,
    ) -> None:
        self.cad = cad
        self.slicer = slicer
        self.profiles = profiles
        self.artifacts = artifacts

    def list_geometries(self) -> list[dict[str, Any]]:
        return self.cad.geometries.list_public()

    def list_profiles(self, *, printer_id: str | None = None) -> list[dict[str, Any]]:
        return self.profiles.list_public(printer_id=printer_id)

    def prepare_print_artifact(
        self,
        *,
        geometry_id: str,
        profile_id: str,
        artifact_id: str,
        output_format: str = "stl",
    ) -> dict[str, Any]:
        render = self.cad.render(geometry_id, output_format=output_format)
        geometry = render.pop("geometry")
        if not isinstance(geometry, bytes):
            raise FabricationValidationError("OpenSCAD pipeline returned invalid geometry bytes")
        profile = self.profiles.get(profile_id)
        sliced = self.slicer.slice_geometry(
            source_filename=render["output_filename"],
            geometry=geometry,
            profile=profile,
        )
        slicer_receipt = sliced.receipt.to_dict()
        provenance = {
            "schema": "hardware_splicer.mechanical_fabrication_provenance.v1",
            "geometry": render,
            "slicer": slicer_receipt,
        }
        provenance_sha = hashlib.sha256(
            json.dumps(provenance, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        artifact = self.artifacts.register(
            artifact_id=artifact_id,
            kind="gcode",
            content=sliced.gcode,
            generator="mechanical_fabrication_pipeline",
            generator_receipt_sha256=provenance_sha,
            metadata={
                "geometry_id": geometry_id,
                "geometry_sha256": slicer_receipt["source_geometry_sha256"],
                "profile_id": profile.profile_id,
                "profile_sha256": profile.sha256,
                "printer_id": profile.printer_id,
                "slicer": slicer_receipt["slicer_name"],
                "slicer_version": slicer_receipt["slicer_version"],
            },
        )
        return {
            "schema": "hardware_splicer.mechanical_print_artifact.v1",
            "artifact": artifact.public_dict(),
            "provenance": provenance,
            "provenance_sha256": provenance_sha,
            "ready_for_physical_staging": True,
            "fabrication_authorized": False,
            "physical_correctness": "UNPROVEN",
        }
