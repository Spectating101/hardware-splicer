"""Bounded agent facade for the fabricator digital-thread tranche.

All raw bytes, paths, endpoints, credentials and executable configuration stay
server-side. The agent selects stable ids and bounded specs only.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .engineering_artifact_store import EngineeringArtifactStore
from .fabrication_digital_thread import FabricationDigitalThread
from .fabrication_operator import FabricationValidationError
from .kicad_fabrication_pipeline import KicadFabricationPipeline
from .mechanical_fabrication_pipeline import MechanicalFabricationPipeline
from .motion_plan_dry_run import MotionPlanDryRun
from .opcua_observer import OpcUaObserver
from .pcb_fabrication_request import PcbFabricationSpec
from .ros2_observer import Ros2GraphObserver
from .stored_handoff_service import StoredHandoffService


class FabricatorDigitalThreadWorkbench:
    def __init__(
        self,
        *,
        artifacts: EngineeringArtifactStore,
        mechanical: MechanicalFabricationPipeline | None = None,
        pcb: KicadFabricationPipeline | None = None,
        opcua_sources: Mapping[str, OpcUaObserver] | None = None,
        ros2_sources: Mapping[str, Ros2GraphObserver] | None = None,
        motion_analyzers: Mapping[str, MotionPlanDryRun] | None = None,
        handoffs: StoredHandoffService | None = None,
        threads: Mapping[str, FabricationDigitalThread] | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.mechanical = mechanical
        self.pcb = pcb
        self.opcua_sources = dict(opcua_sources or {})
        self.ros2_sources = dict(ros2_sources or {})
        self.motion_analyzers = dict(motion_analyzers or {})
        self.handoffs = handoffs or StoredHandoffService(artifacts=artifacts)
        self.threads = dict(threads or {})

    def list_artifacts(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        return self.artifacts.list_public(kind=kind)

    def list_mechanical_geometries(self) -> list[dict[str, Any]]:
        if self.mechanical is None:
            raise FabricationValidationError("mechanical fabrication integration is not configured")
        return self.mechanical.list_geometries()

    def list_slicer_profiles(self, *, printer_id: str | None = None) -> list[dict[str, Any]]:
        if self.mechanical is None:
            raise FabricationValidationError("mechanical fabrication integration is not configured")
        return self.mechanical.list_profiles(printer_id=printer_id)

    def prepare_print_artifact(
        self,
        *,
        geometry_id: str,
        profile_id: str,
        artifact_id: str,
        output_format: str = "stl",
    ) -> dict[str, Any]:
        if self.mechanical is None:
            raise FabricationValidationError("mechanical fabrication integration is not configured")
        return self.mechanical.prepare_print_artifact(
            geometry_id=geometry_id,
            profile_id=profile_id,
            artifact_id=artifact_id,
            output_format=output_format,
        )

    def opcua_measurements(self, source_id: str) -> list[dict[str, Any]]:
        source = self._source(self.opcua_sources, source_id, "OPC UA")
        return source.measurements.list_public()

    def opcua_read(self, source_id: str, *, measurement_ids: Sequence[str]) -> dict[str, Any]:
        source = self._source(self.opcua_sources, source_id, "OPC UA")
        return source.read(measurement_ids)

    def ros2_graph(self, source_id: str) -> dict[str, Any]:
        source = self._source(self.ros2_sources, source_id, "ROS 2")
        return source.capture_graph()

    def dry_run_motion_plan(self, analyzer_id: str, *, artifact_id: str) -> dict[str, Any]:
        analyzer = self._source(self.motion_analyzers, analyzer_id, "motion-plan analyzer")
        return analyzer.analyze(artifact_id)

    def prepare_pcb_request(
        self,
        *,
        project_id: str,
        revision_id: str,
        request_artifact_id: str,
        spec: Mapping[str, Any],
    ) -> dict[str, Any]:
        if self.pcb is None:
            raise FabricationValidationError("PCB fabrication integration is not configured")
        if not isinstance(spec, Mapping):
            raise FabricationValidationError("PCB fabrication spec must be an object")
        try:
            normalized = PcbFabricationSpec(**dict(spec))
        except TypeError as exc:
            raise FabricationValidationError("PCB fabrication spec has invalid fields") from exc
        return self.pcb.prepare_request(
            project_id=project_id,
            revision_id=revision_id,
            request_artifact_id=request_artifact_id,
            spec=normalized,
        )

    def build_handoff(
        self,
        *,
        project_id: str,
        mission_id: str,
        revision_id: str,
        source_artifact_ids: Sequence[str],
        output_artifact_id: str,
    ) -> dict[str, Any]:
        return self.handoffs.build(
            project_id=project_id,
            mission_id=mission_id,
            revision_id=revision_id,
            source_artifact_ids=source_artifact_ids,
            output_artifact_id=output_artifact_id,
        )

    def thread_manifest(self, thread_id: str) -> dict[str, Any]:
        return self._thread(thread_id).manifest()

    def thread_trace(self, thread_id: str, *, artifact_id: str) -> dict[str, Any]:
        return self._thread(thread_id).trace_artifact(artifact_id)

    @staticmethod
    def _source(values: Mapping[str, Any], key: str, label: str) -> Any:
        if not isinstance(key, str) or not key.strip():
            raise FabricationValidationError(f"{label} id is required")
        try:
            return values[key.strip()]
        except KeyError as exc:
            raise FabricationValidationError(f"unknown {label} id") from exc

    def _thread(self, thread_id: str) -> FabricationDigitalThread:
        value = self._source(self.threads, thread_id, "digital thread")
        if not isinstance(value, FabricationDigitalThread):
            raise FabricationValidationError("configured digital thread is invalid")
        return value
