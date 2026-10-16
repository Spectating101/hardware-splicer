"""Bounded KiCad BOM export for manufacturing/procurement handoff.

Kept separate from the base KiCad operator so the existing verification/export
contract remains stable. The agent selects only a registered KiCad project id;
fields, output path and argv are server-defined.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Protocol

from .fabrication_operator import FabricationValidationError
from .kicad_cli_operator import KicadProjectRegistry


class KicadBomExecutionError(RuntimeError):
    pass


class KicadBomRunner(Protocol):
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[str]: ...


class SubprocessKicadBomRunner:
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(argv, cwd=str(cwd), check=False, capture_output=True, text=True, shell=False, timeout=timeout_seconds)


class KicadBomOperator:
    def __init__(
        self,
        *,
        projects: KicadProjectRegistry,
        executable: str = "kicad-cli",
        runner: KicadBomRunner | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        if not isinstance(executable, str) or not executable.strip() or any(ch in executable for ch in "\r\n\x00"):
            raise FabricationValidationError("KiCad executable must be server-configured text")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 1 <= float(timeout_seconds) <= 1800:
            raise FabricationValidationError("KiCad BOM timeout must be between 1 and 1800 seconds")
        self.projects = projects
        self.executable = executable.strip()
        self.runner = runner or SubprocessKicadBomRunner()
        self.timeout_seconds = float(timeout_seconds)

    def export(self, project_id: str) -> dict[str, Any]:
        project = self.projects.get(project_id)
        if project.schematic is None:
            raise FabricationValidationError("KiCad BOM export requires a registered schematic")
        with tempfile.TemporaryDirectory(prefix="hs-kicad-bom-") as temp_dir:
            output = Path(temp_dir) / "bom.csv"
            argv = [
                self.executable,
                "sch",
                "export",
                "bom",
                "--output",
                str(output),
                "--fields",
                "Reference,Value,Footprint,QUANTITY,DNP",
                str(project.schematic),
            ]
            try:
                completed = self.runner.run(argv, cwd=project.root, timeout_seconds=self.timeout_seconds)
            except (OSError, subprocess.SubprocessError) as exc:
                raise KicadBomExecutionError("KiCad BOM export failed") from exc
            if completed.returncode != 0:
                raise KicadBomExecutionError(
                    f"KiCad BOM export exited with {completed.returncode}: {(completed.stderr or '')[-1000:]}"
                )
            if not output.is_file() or output.is_symlink():
                raise KicadBomExecutionError("KiCad BOM export did not create a regular file")
            data = output.read_bytes()
            if not data:
                raise KicadBomExecutionError("KiCad BOM export created an empty file")
            return {
                "schema": "hardware_splicer.kicad_bom_receipt.v1",
                "project_id": project.project_id,
                "tool": "kicad-cli",
                "output_filename": "bom.csv",
                "output_sha256": hashlib.sha256(data).hexdigest(),
                "output_size_bytes": len(data),
                "bom": data,
                "argv_shape": [
                    "kicad-cli", "sch", "export", "bom", "--output", "<server-temp-output>",
                    "--fields", "Reference,Value,Footprint,QUANTITY,DNP", "<registered-schematic>",
                ],
                "physical_correctness": "UNPROVEN",
            }
