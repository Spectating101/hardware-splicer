"""Trusted geometry-to-printer handoff for Hardware Splicer fabrication.

The raw printer operator can stage G-code because it is also useful to trusted
server-side code.  Agent-facing fabrication should use this pipeline instead:
it accepts only a server-created ``SlicedArtifact``, re-hashes the G-code,
checks the receipt/printer binding, and records a canonical receipt hash before
staging the exact bytes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .fabrication_operator import FabricationValidationError
from .printer_operator import FabricationPrinter, PreparedPrint, PrintRun
from .slicer_operator import SlicedArtifact, SlicerReceipt


def _receipt_sha256(receipt: SlicerReceipt) -> str:
    payload = json.dumps(
        receipt.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class StagedFabrication:
    schema: str
    prepared: PreparedPrint
    slicer_receipt: SlicerReceipt
    slicer_receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "prepared": asdict(self.prepared),
            "slicer_receipt": self.slicer_receipt.to_dict(),
            "slicer_receipt_sha256": self.slicer_receipt_sha256,
        }


class FabricationPipeline:
    """Binds slicer provenance to one configured physical printer."""

    def __init__(self, printer: FabricationPrinter):
        if not isinstance(printer, FabricationPrinter):
            raise FabricationValidationError("fabrication pipeline requires a configured FabricationPrinter")
        self.printer = printer

    def stage_sliced(
        self,
        artifact: SlicedArtifact,
        *,
        filename: str | None = None,
    ) -> StagedFabrication:
        if not isinstance(artifact, SlicedArtifact):
            raise FabricationValidationError("stage requires a server-created SlicedArtifact")
        receipt = artifact.receipt
        if receipt.printer_id != self.printer.printer_id:
            raise FabricationValidationError("slicer receipt belongs to a different printer")
        actual = hashlib.sha256(artifact.gcode).hexdigest()
        if actual != receipt.output_gcode_sha256:
            raise FabricationValidationError("G-code bytes do not match the slicer receipt")
        safe_name = filename
        if safe_name is None:
            safe_name = f"{Path(receipt.source_filename).stem}.gcode"
        prepared = self.printer.stage_gcode(filename=safe_name, data=artifact.gcode)
        if prepared.artifact_sha256 != receipt.output_gcode_sha256:
            raise FabricationValidationError("staged printer artifact does not match the slicer receipt")
        return StagedFabrication(
            schema="hardware_splicer.staged_fabrication.v1",
            prepared=prepared,
            slicer_receipt=receipt,
            slicer_receipt_sha256=_receipt_sha256(receipt),
        )

    def start(
        self,
        staged: StagedFabrication,
        *,
        project_id: str,
        mission_id: str,
        grant_id: str,
    ) -> PrintRun:
        self._validate_staged(staged)
        return self.printer.start(
            staged.prepared,
            project_id=project_id,
            mission_id=mission_id,
            grant_id=grant_id,
        )

    def _validate_staged(self, staged: StagedFabrication) -> None:
        if not isinstance(staged, StagedFabrication):
            raise FabricationValidationError("operation requires a server-created StagedFabrication")
        if staged.prepared.printer_id != self.printer.printer_id:
            raise FabricationValidationError("staged fabrication belongs to a different printer")
        if staged.slicer_receipt.printer_id != self.printer.printer_id:
            raise FabricationValidationError("slicer receipt belongs to a different printer")
        if staged.prepared.artifact_sha256 != staged.slicer_receipt.output_gcode_sha256:
            raise FabricationValidationError("staged G-code hash no longer matches the slicer receipt")
        if staged.slicer_receipt_sha256 != _receipt_sha256(staged.slicer_receipt):
            raise FabricationValidationError("slicer receipt has changed since staging")
