"""Registered KiCad project -> stored vendor-neutral PCB fabrication request.

This pipeline keeps raw manufacturing bytes server-side. It runs fixed KiCad CLI
exports into a temporary directory, builds a deterministic PCB request package,
and stores the package as a non-executable engineering artifact. No vendor is
selected and no order is submitted.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Protocol

from .engineering_artifact_store import EngineeringArtifactStore
from .fabrication_operator import FabricationValidationError
from .kicad_cli_operator import KicadProjectRegistry
from .pcb_fabrication_request import PcbFabricationRequestBuilder, PcbFabricationSpec


class KicadFabricationExecutionError(RuntimeError):
    pass


class KicadFabricationRunner(Protocol):
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[str]: ...


class SubprocessKicadFabricationRunner:
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(argv, cwd=str(cwd), check=False, capture_output=True, text=True, shell=False, timeout=timeout_seconds)


class KicadFabricationPipeline:
    def __init__(
        self,
        *,
        projects: KicadProjectRegistry,
        artifacts: EngineeringArtifactStore,
        executable: str = "kicad-cli",
        runner: KicadFabricationRunner | None = None,
        timeout_seconds: float = 180.0,
    ) -> None:
        if not isinstance(executable, str) or not executable.strip() or any(ch in executable for ch in "\r\n\x00"):
            raise FabricationValidationError("KiCad executable must be server-configured text")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 1 <= float(timeout_seconds) <= 1800:
            raise FabricationValidationError("KiCad fabrication timeout must be between 1 and 1800 seconds")
        self.projects = projects
        self.artifacts = artifacts
        self.executable = executable.strip()
        self.runner = runner or SubprocessKicadFabricationRunner()
        self.timeout_seconds = float(timeout_seconds)
        self.builder = PcbFabricationRequestBuilder()

    def prepare_request(
        self,
        *,
        project_id: str,
        revision_id: str,
        request_artifact_id: str,
        spec: PcbFabricationSpec,
    ) -> dict[str, Any]:
        project = self.projects.get(project_id)
        if project.board is None:
            raise FabricationValidationError("PCB fabrication request requires a KiCad board")
        if spec.assembly_requested and project.schematic is None:
            raise FabricationValidationError("assembled PCB request requires a KiCad schematic for BOM export")
        with tempfile.TemporaryDirectory(prefix="hs-kicad-fab-") as temp_dir:
            root = Path(temp_dir)
            gerber_dir = root / "gerbers"
            drill_dir = root / "drill"
            gerber_dir.mkdir()
            drill_dir.mkdir()
            positions = root / "positions.csv"
            commands = [
                [self.executable, "pcb", "export", "gerbers", "--output", str(gerber_dir), str(project.board)],
                [self.executable, "pcb", "export", "drill", "--output", str(drill_dir), str(project.board)],
                [self.executable, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--output", str(positions), str(project.board)],
            ]
            bom: Path | None = None
            if project.schematic is not None:
                bom = root / "bom.csv"
                commands.append([
                    self.executable, "sch", "export", "bom", "--output", str(bom),
                    "--fields", "Reference,Value,Footprint,QUANTITY,DNP", str(project.schematic),
                ])
            receipts = [self._run(argv, cwd=project.root) for argv in commands]
            gerbers = _collect(gerber_dir, {".gbr", ".ger", ".pho"})
            drills = _collect(drill_dir, {".drl", ".xln", ".txt"})
            positions_bytes = positions.read_bytes() if positions.is_file() and not positions.is_symlink() else None
            bom_bytes = bom.read_bytes() if bom is not None and bom.is_file() and not bom.is_symlink() else None
            request = self.builder.build(
                project_id=project_id,
                revision_id=revision_id,
                spec=spec,
                gerbers=gerbers,
                drill_files=drills,
                bom_csv=bom_bytes,
                positions_csv=positions_bytes,
                notes={
                    "generated_by": "kicad_fabrication_pipeline",
                    "tool_receipts": receipts,
                },
            )
        stored = self.artifacts.put(
            artifact_id=request_artifact_id,
            kind="pcb_fab_request",
            content=request["package"],
            media_type="application/zip",
            producer="kicad_fabrication_pipeline",
            metadata={
                "project_id": project_id,
                "revision_id": revision_id,
                "request_manifest": request["manifest"],
                "package_sha256": request["package_sha256"],
            },
        )
        return {
            "schema": "hardware_splicer.stored_pcb_fabrication_request.v1",
            "artifact": stored.public_dict(),
            "request_manifest": request["manifest"],
            "vendor_selected": False,
            "quote_requested": False,
            "order_submitted": False,
            "physical_correctness": "UNPROVEN",
        }

    def _run(self, argv: list[str], *, cwd: Path) -> dict[str, Any]:
        try:
            completed = self.runner.run(argv, cwd=cwd, timeout_seconds=self.timeout_seconds)
        except (OSError, subprocess.SubprocessError) as exc:
            raise KicadFabricationExecutionError("KiCad fabrication export failed") from exc
        if completed.returncode != 0:
            raise KicadFabricationExecutionError(
                f"KiCad fabrication export exited with {completed.returncode}: {(completed.stderr or '')[-1000:]}"
            )
        return {
            "argv_shape": _argv_shape(argv),
            "exit_code": int(completed.returncode),
            "stdout_sha256": hashlib.sha256((completed.stdout or "").encode("utf-8", errors="replace")).hexdigest(),
            "stderr_sha256": hashlib.sha256((completed.stderr or "").encode("utf-8", errors="replace")).hexdigest(),
        }


def _collect(directory: Path, suffixes: set[str]) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for path in sorted(directory.iterdir()) if directory.is_dir() else []:
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in suffixes:
            result[path.name] = path.read_bytes()
    if not result:
        raise KicadFabricationExecutionError("KiCad export did not produce required manufacturing files")
    return result


def _argv_shape(argv: list[str]) -> list[str]:
    # Do not persist server filesystem paths in public provenance.
    shaped: list[str] = []
    for token in argv:
        if "/" in token or "\\" in token:
            shaped.append("<server-path>")
        else:
            shaped.append(token)
    return shaped
