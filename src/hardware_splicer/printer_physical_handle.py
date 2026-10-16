"""Bridge the concrete printer adapter into the generic physical control plane.

The generic dispatcher owns human authority.  This private handle therefore
uses the lower-level printer backend only after the dispatcher has consumed the
exact plan grant.  Staging remains a separate non-actuating operation and
accepts only a registered immutable G-code artifact.
"""

from __future__ import annotations

from typing import Any, Mapping

from .fabrication_operator import FabricationValidationError
from .physical_artifact import PhysicalArtifactRegistry
from .physical_operator import PhysicalExecutionPlan
from .printer_operator import FabricationPrinter, PreparedPrint


class PrinterPhysicalHandle:
    def __init__(self, *, printer: FabricationPrinter, artifacts: PhysicalArtifactRegistry):
        if not isinstance(printer, FabricationPrinter):
            raise FabricationValidationError("printer physical handle requires FabricationPrinter")
        if not isinstance(artifacts, PhysicalArtifactRegistry):
            raise FabricationValidationError("printer physical handle requires PhysicalArtifactRegistry")
        self.printer = printer
        self.artifacts = artifacts
        self._staged: dict[str, PreparedPrint] = {}

    def execute(self, plan: PhysicalExecutionPlan) -> Mapping[str, Any]:
        if not isinstance(plan, PhysicalExecutionPlan) or plan.operator_kind != "printer":
            raise FabricationValidationError("printer handle requires a printer execution plan")
        if plan.operator_id != self.printer.printer_id:
            raise FabricationValidationError("printer execution plan targets a different printer")

        if plan.action == "status":
            return self.printer.status()
        if plan.action == "stage":
            artifact = self._artifact_from_payload(plan)
            if artifact.kind != "gcode":
                raise FabricationValidationError("printer stage requires a registered G-code artifact")
            data = self.artifacts.bytes(artifact.artifact_id)
            filename = self._stage_filename(plan.payload, artifact.artifact_id)
            prepared = self.printer.stage_gcode(filename=filename, data=data)
            if prepared.artifact_sha256 != artifact.sha256:
                raise FabricationValidationError("staged printer bytes do not match registered artifact")
            self._staged[artifact.sha256] = prepared
            return {
                "schema": "hardware_splicer.generic_printer_stage.v1",
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact.sha256,
                "prepared": prepared.to_dict(),
            }
        if plan.action in {"start", "resume"}:
            artifact = self.artifacts.verify_plan_artifact(plan)
            prepared = self._staged.get(artifact.sha256)
            if prepared is None:
                raise FabricationValidationError("printer artifact must be staged before actuation")
            if plan.action == "start":
                response = self.printer.backend.start(self.printer.transport, prepared)
            else:
                response = self.printer.backend.resume(self.printer.transport)
            return {
                "schema": "hardware_splicer.generic_printer_actuation.v1",
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact.sha256,
                "remote_path": prepared.remote_path,
                "backend_result": dict(response),
            }
        if plan.action == "pause":
            return dict(self.printer.backend.pause(self.printer.transport))
        if plan.action == "cancel":
            return dict(self.printer.backend.cancel(self.printer.transport))
        raise FabricationValidationError(f"unsupported printer physical action {plan.action!r}")

    def _artifact_from_payload(self, plan: PhysicalExecutionPlan):
        if not isinstance(plan.payload, Mapping):
            raise FabricationValidationError("printer plan payload is invalid")
        artifact_id = plan.payload.get("artifact_id")
        if not isinstance(artifact_id, str):
            raise FabricationValidationError("printer stage requires artifact_id")
        descriptor = self.artifacts.describe(artifact_id)
        # Re-read through verifyable server registry rather than trusting payload hashes.
        class _ArtifactView:
            pass
        view = _ArtifactView()
        view.artifact_id = descriptor["artifact_id"]
        view.kind = descriptor["kind"]
        view.sha256 = descriptor["sha256"]
        return view

    @staticmethod
    def _stage_filename(payload: Mapping[str, Any], artifact_id: str) -> str:
        filename = payload.get("filename") if isinstance(payload, Mapping) else None
        if filename is None:
            return f"{artifact_id}.gcode"
        if not isinstance(filename, str) or not filename.strip():
            raise FabricationValidationError("printer stage filename must be a string")
        return filename.strip()
