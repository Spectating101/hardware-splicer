"""Bounded headless FreeCAD export for registered precision-CAD models.

Agents select a server-registered FCStd model and output format. The adapter
creates a fixed Python export script in a private temporary directory and invokes
a server-configured FreeCADCmd executable without a shell. No agent-supplied
Python, macro, filesystem path or command string is executed.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .engineering_artifact_store import EngineeringArtifactStore
from .fabrication_operator import FabricationValidationError


class FreeCadExecutionError(RuntimeError):
    pass


class FreeCadRunner(Protocol):
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[bytes]: ...


class SubprocessFreeCadRunner:
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(argv, cwd=str(cwd), check=False, capture_output=True, shell=False, timeout=timeout_seconds)


@dataclass(frozen=True)
class FreeCadModel:
    model_id: str
    source: Path


class FreeCadModelRegistry:
    def __init__(self) -> None:
        self._models: dict[str, FreeCadModel] = {}

    def register(self, *, model_id: str, source: str | Path) -> None:
        mid = _id(model_id, "model_id")
        if mid in self._models:
            raise FabricationValidationError("FreeCAD model id is already registered")
        literal = Path(source)
        if literal.is_symlink():
            raise FabricationValidationError("FreeCAD source must not be a symlink")
        path = literal.resolve()
        if not path.is_file() or path.suffix.lower() != ".fcstd":
            raise FabricationValidationError("FreeCAD source must be an existing FCStd file")
        self._models[mid] = FreeCadModel(mid, path)

    def get(self, model_id: str) -> FreeCadModel:
        try:
            return self._models[model_id]
        except KeyError as exc:
            raise FabricationValidationError("unknown FreeCAD model id") from exc

    def list_public(self) -> list[dict[str, Any]]:
        return [
            {
                "model_id": row.model_id,
                "source_sha256": hashlib.sha256(row.source.read_bytes()).hexdigest(),
                "output_formats": ["step", "stl"],
            }
            for row in sorted(self._models.values(), key=lambda item: item.model_id)
        ]


_EXPORT_SCRIPT = r'''import sys
import FreeCAD as App
import Part
import Mesh
source, output, fmt = sys.argv[-3], sys.argv[-2], sys.argv[-1]
doc = App.openDocument(source)
try:
    objects = [obj for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
    if not objects:
        raise RuntimeError("document has no exportable shapes")
    if fmt == "step":
        Part.export(objects, output)
    elif fmt == "stl":
        Mesh.export(objects, output)
    else:
        raise RuntimeError("unsupported export format")
finally:
    App.closeDocument(doc.Name)
'''


class FreeCadExportOperator:
    def __init__(
        self,
        *,
        models: FreeCadModelRegistry,
        artifacts: EngineeringArtifactStore,
        executable: str = "FreeCADCmd",
        version: str = "configured",
        runner: FreeCadRunner | None = None,
        timeout_seconds: float = 300.0,
    ) -> None:
        if not isinstance(executable, str) or not executable.strip() or any(ch in executable for ch in "\r\n\x00"):
            raise FabricationValidationError("FreeCAD executable must be server-configured text")
        if not isinstance(version, str) or not version.strip() or len(version.strip()) > 128:
            raise FabricationValidationError("FreeCAD version must be bounded text")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 1 <= float(timeout_seconds) <= 3600:
            raise FabricationValidationError("FreeCAD timeout must be between 1 and 3600 seconds")
        self.models = models
        self.artifacts = artifacts
        self.executable = executable.strip()
        self.version = version.strip()
        self.runner = runner or SubprocessFreeCadRunner()
        self.timeout_seconds = float(timeout_seconds)

    def export(self, *, model_id: str, output_format: str, artifact_id: str) -> dict[str, Any]:
        if output_format not in {"step", "stl"}:
            raise FabricationValidationError("FreeCAD output_format must be step or stl")
        model = self.models.get(model_id)
        source_sha = hashlib.sha256(model.source.read_bytes()).hexdigest()
        suffix = ".step" if output_format == "step" else ".stl"
        media_type = "model/step" if output_format == "step" else "model/stl"
        with tempfile.TemporaryDirectory(prefix="hs-freecad-") as temp_dir:
            root = Path(temp_dir)
            script = root / "export_model.py"
            output = root / f"model{suffix}"
            script.write_text(_EXPORT_SCRIPT, encoding="utf-8")
            argv = [self.executable, str(script), str(model.source), str(output), output_format]
            try:
                completed = self.runner.run(argv, cwd=root, timeout_seconds=self.timeout_seconds)
            except (OSError, subprocess.SubprocessError) as exc:
                raise FreeCadExecutionError("FreeCAD headless export failed") from exc
            stdout = bytes(completed.stdout or b"")
            stderr = bytes(completed.stderr or b"")
            if completed.returncode != 0:
                message = (stderr or stdout).decode("utf-8", errors="replace")[-1000:]
                raise FreeCadExecutionError(f"FreeCAD exited with {completed.returncode}: {message}")
            if not output.is_file() or output.is_symlink():
                raise FreeCadExecutionError("FreeCAD did not create a regular export file")
            payload = output.read_bytes()
            if not payload:
                raise FreeCadExecutionError("FreeCAD created an empty export")
        stored = self.artifacts.put(
            artifact_id=artifact_id,
            kind="geometry",
            content=payload,
            media_type=media_type,
            producer="freecad",
            metadata={
                "model_id": model.model_id,
                "source_sha256": source_sha,
                "output_format": output_format,
                "tool_version": self.version,
                "script_sha256": hashlib.sha256(_EXPORT_SCRIPT.encode("utf-8")).hexdigest(),
                "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            },
        )
        return {
            "schema": "hardware_splicer.freecad_export_receipt.v1",
            "artifact": stored.public_dict(),
            "model_id": model.model_id,
            "source_sha256": source_sha,
            "output_format": output_format,
            "physical_correctness": "UNPROVEN",
        }


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
