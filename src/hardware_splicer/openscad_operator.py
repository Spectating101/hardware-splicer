"""Bounded OpenSCAD renderer for existing Mecha-Splicer geometry.

Hardware Splicer already produces OpenSCAD mechanical artifacts. This adapter
bridges those server-registered sources into immutable STL/3MF bytes that can be
fed directly into the existing slicer provenance pipeline. Agents select a
registered geometry id and output format; they never supply shell text, source
paths, executable paths, or arbitrary OpenSCAD source through this surface.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .fabrication_operator import FabricationValidationError


class OpenScadExecutionError(RuntimeError):
    pass


class OpenScadRunner(Protocol):
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[bytes]: ...


class SubprocessOpenScadRunner:
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            argv,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            shell=False,
            timeout=timeout_seconds,
        )


@dataclass(frozen=True)
class OpenScadGeometry:
    geometry_id: str
    root: Path
    source: Path


class OpenScadGeometryRegistry:
    def __init__(self) -> None:
        self._items: dict[str, OpenScadGeometry] = {}

    def register(self, *, geometry_id: str, root: str | Path, source: str | Path) -> None:
        gid = _id(geometry_id, "geometry_id")
        if gid in self._items:
            raise FabricationValidationError("OpenSCAD geometry id is already registered")
        root_literal = Path(root)
        if root_literal.is_symlink():
            raise FabricationValidationError("OpenSCAD root must not be a symlink")
        root_path = root_literal.resolve()
        if not root_path.is_dir():
            raise FabricationValidationError("OpenSCAD root must be an existing directory")
        raw = Path(source)
        candidate = raw if raw.is_absolute() else root_path / raw
        if candidate.is_symlink():
            raise FabricationValidationError("OpenSCAD source must not be a symlink")
        source_path = candidate.resolve()
        try:
            source_path.relative_to(root_path)
        except ValueError as exc:
            raise FabricationValidationError("OpenSCAD source escapes registered root") from exc
        if not source_path.is_file() or source_path.suffix.lower() != ".scad":
            raise FabricationValidationError("OpenSCAD source must be an existing .scad file")
        self._items[gid] = OpenScadGeometry(gid, root_path, source_path)

    def get(self, geometry_id: str) -> OpenScadGeometry:
        try:
            return self._items[geometry_id]
        except KeyError as exc:
            raise FabricationValidationError("unknown OpenSCAD geometry id") from exc

    def list_public(self) -> list[dict[str, Any]]:
        return [
            {
                "geometry_id": row.geometry_id,
                "source_sha256": _sha(row.source.read_bytes()),
                "output_formats": ["stl", "3mf"],
            }
            for row in sorted(self._items.values(), key=lambda item: item.geometry_id)
        ]


class OpenScadOperator:
    def __init__(
        self,
        *,
        geometries: OpenScadGeometryRegistry,
        executable: str = "openscad",
        version: str = "configured",
        runner: OpenScadRunner | None = None,
        timeout_seconds: float = 300.0,
    ):
        if not isinstance(executable, str) or not executable.strip() or any(ch in executable for ch in "\r\n\x00"):
            raise FabricationValidationError("OpenSCAD executable must be server-configured text")
        if not isinstance(version, str) or not version.strip() or len(version.strip()) > 128:
            raise FabricationValidationError("OpenSCAD version must be bounded text")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 1 <= float(timeout_seconds) <= 3600:
            raise FabricationValidationError("OpenSCAD timeout must be between 1 and 3600 seconds")
        self.geometries = geometries
        self.executable = executable.strip()
        self.version = version.strip()
        self.runner = runner or SubprocessOpenScadRunner()
        self.timeout_seconds = float(timeout_seconds)

    def render(self, geometry_id: str, *, output_format: str = "stl") -> dict[str, Any]:
        if output_format not in {"stl", "3mf"}:
            raise FabricationValidationError("OpenSCAD output_format must be stl or 3mf")
        item = self.geometries.get(geometry_id)
        source_bytes = item.source.read_bytes()
        if not source_bytes:
            raise FabricationValidationError("OpenSCAD source is empty")
        with tempfile.TemporaryDirectory(prefix="hs-openscad-") as temp_dir:
            output = Path(temp_dir) / f"geometry.{output_format}"
            argv = [self.executable, "-o", str(output), str(item.source)]
            try:
                completed = self.runner.run(argv, cwd=item.root, timeout_seconds=self.timeout_seconds)
            except (OSError, subprocess.SubprocessError) as exc:
                raise OpenScadExecutionError("OpenSCAD execution failed") from exc
            if completed.returncode != 0:
                stderr = (completed.stderr or b"").decode("utf-8", errors="replace")[-1000:]
                raise OpenScadExecutionError(f"OpenSCAD exited with {completed.returncode}: {stderr}")
            if not output.is_file() or output.is_symlink():
                raise OpenScadExecutionError("OpenSCAD did not create a regular geometry output")
            payload = output.read_bytes()
            if not payload:
                raise OpenScadExecutionError("OpenSCAD created an empty geometry output")
            stdout = bytes(completed.stdout or b"")
            stderr = bytes(completed.stderr or b"")
            return {
                "schema": "hardware_splicer.openscad_render_receipt.v1",
                "geometry_id": item.geometry_id,
                "tool": "openscad",
                "tool_version": self.version,
                "output_format": output_format,
                "source_sha256": _sha(source_bytes),
                "output_sha256": _sha(payload),
                "output_size_bytes": len(payload),
                "output_filename": f"{item.source.stem}.{output_format}",
                "geometry": payload,
                "argv_shape": ["openscad", "-o", "<server-temp-output>", "<registered-source>"],
                "stdout_sha256": _sha(stdout),
                "stderr_sha256": _sha(stderr),
                "physical_correctness": "UNPROVEN",
            }


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 96 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
