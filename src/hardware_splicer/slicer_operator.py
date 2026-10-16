"""Deterministic slicer boundary for physical-fabrication missions.

A slicer is not allowed to create physical authority.  Its job is narrower:
turn one immutable geometry artifact plus one server-approved printer/material
profile into G-code and emit a receipt that cryptographically binds every
input to the exact bytes a printer may later stage.

The language-model/mission layer may choose among registered profiles, but it
must not synthesize executable paths, shell commands, or profile bytes.  Real
slicer execution therefore sits behind an injected runner.  Tests can use a
fake runner; the production PrusaSlicer runner invokes a server-configured
binary with a fixed argv shape and never uses a shell.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from .fabrication_operator import FabricationValidationError

_GEOMETRY_SUFFIXES = frozenset({".stl", ".3mf", ".obj", ".amf"})
_PROFILE_SUFFIXES = frozenset({".ini", ".config", ".cfg"})


class SlicerExecutionError(RuntimeError):
    """The configured slicer failed to produce a valid G-code artifact."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _payload(value: bytes | bytearray, *, field: str) -> bytes:
    if not isinstance(value, (bytes, bytearray)) or not value:
        raise FabricationValidationError(f"{field} must be non-empty bytes")
    return bytes(value)


def _basename(value: str, *, field: str, suffixes: frozenset[str]) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip().replace("\\", "/").split("/")[-1]
    if not cleaned or cleaned in {".", ".."} or len(cleaned) > 180:
        raise FabricationValidationError(f"{field} must be a bounded basename")
    if any(ord(ch) < 32 for ch in cleaned):
        raise FabricationValidationError(f"{field} must not contain control characters")
    if Path(cleaned).suffix.lower() not in suffixes:
        raise FabricationValidationError(f"{field} has an unsupported file type")
    return cleaned


def _identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128:
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    if any(ch.isspace() for ch in cleaned):
        raise FabricationValidationError(f"{field} must not contain whitespace")
    return cleaned


@dataclass(frozen=True)
class SlicerProfile:
    """Server-created profile artifact; agents select by id rather than bytes."""

    profile_id: str
    printer_id: str
    filename: str
    content: bytes
    material: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _identifier(self.profile_id, field="profile_id"))
        object.__setattr__(self, "printer_id", _identifier(self.printer_id, field="printer_id"))
        object.__setattr__(
            self,
            "filename",
            _basename(self.filename, field="profile filename", suffixes=_PROFILE_SUFFIXES),
        )
        object.__setattr__(self, "content", _payload(self.content, field="profile content"))
        if self.material is not None:
            if not isinstance(self.material, str) or not self.material.strip() or len(self.material.strip()) > 80:
                raise FabricationValidationError("profile material must be a bounded string")
            object.__setattr__(self, "material", self.material.strip())

    @property
    def sha256(self) -> str:
        return _digest(self.content)

    def public_descriptor(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "printer_id": self.printer_id,
            "material": self.material,
            "profile_sha256": self.sha256,
        }


@dataclass(frozen=True)
class SlicerReceipt:
    schema: str
    slicer_name: str
    slicer_version: str
    printer_id: str
    profile_id: str
    profile_sha256: str
    source_filename: str
    source_geometry_sha256: str
    output_gcode_sha256: str
    output_size_bytes: int
    estimates: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["estimates"] = json.loads(json.dumps(dict(self.estimates)))
        return value


@dataclass(frozen=True)
class SlicedArtifact:
    receipt: SlicerReceipt
    gcode: bytes


class SlicerRunner(Protocol):
    name: str
    version: str

    def slice(
        self,
        *,
        source_filename: str,
        geometry: bytes,
        profile: SlicerProfile,
    ) -> tuple[bytes, Mapping[str, Any]]: ...


class SlicerOperator:
    """Hashes slicer inputs and emits an immutable provenance receipt."""

    def __init__(self, runner: SlicerRunner):
        self.runner = runner

    def slice_geometry(
        self,
        *,
        source_filename: str,
        geometry: bytes | bytearray,
        profile: SlicerProfile,
    ) -> SlicedArtifact:
        if not isinstance(profile, SlicerProfile):
            raise FabricationValidationError("slice requires a server-created SlicerProfile")
        safe_name = _basename(source_filename, field="source filename", suffixes=_GEOMETRY_SUFFIXES)
        source = _payload(geometry, field="geometry")
        result, estimates = self.runner.slice(
            source_filename=safe_name,
            geometry=source,
            profile=profile,
        )
        gcode = _payload(result, field="slicer G-code output")
        if not isinstance(estimates, Mapping):
            raise SlicerExecutionError("slicer estimates must be an object")
        receipt = SlicerReceipt(
            schema="hardware_splicer.slicer_receipt.v1",
            slicer_name=_identifier(self.runner.name, field="slicer name"),
            slicer_version=_identifier(self.runner.version, field="slicer version"),
            printer_id=profile.printer_id,
            profile_id=profile.profile_id,
            profile_sha256=profile.sha256,
            source_filename=safe_name,
            source_geometry_sha256=_digest(source),
            output_gcode_sha256=_digest(gcode),
            output_size_bytes=len(gcode),
            estimates=json.loads(json.dumps(dict(estimates))),
        )
        return SlicedArtifact(receipt=receipt, gcode=gcode)


class PrusaSlicerRunner:
    """Fixed-argv PrusaSlicer CLI runner.

    The executable and version are server configuration.  Geometry/profile
    filenames are reduced to bounded basenames before they enter a temporary
    directory; no user/model value is interpreted by a shell.
    """

    name = "prusa_slicer"

    def __init__(self, executable: str, *, version: str, timeout_seconds: int = 300):
        if not isinstance(executable, str) or not executable.strip():
            raise FabricationValidationError("PrusaSlicer executable is required")
        self.executable = executable.strip()
        self.version = _identifier(version, field="slicer version")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600:
            raise FabricationValidationError("slicer timeout must be an integer from 1 to 3600 seconds")
        self.timeout_seconds = timeout_seconds

    def slice(
        self,
        *,
        source_filename: str,
        geometry: bytes,
        profile: SlicerProfile,
    ) -> tuple[bytes, Mapping[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="hs-slicer-") as temp_dir:
            root = Path(temp_dir)
            source_path = root / source_filename
            profile_path = root / profile.filename
            output_path = root / f"{Path(source_filename).stem}.gcode"
            source_path.write_bytes(geometry)
            profile_path.write_bytes(profile.content)
            argv = [
                self.executable,
                "--export-gcode",
                "--load",
                str(profile_path),
                "--output",
                str(output_path),
                str(source_path),
            ]
            try:
                completed = subprocess.run(
                    argv,
                    cwd=root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=self.timeout_seconds,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise SlicerExecutionError("PrusaSlicer execution failed") from exc
            if completed.returncode != 0:
                stderr = completed.stderr.decode("utf-8", errors="replace")[-1000:]
                raise SlicerExecutionError(f"PrusaSlicer exited with {completed.returncode}: {stderr}")
            if not output_path.exists():
                raise SlicerExecutionError("PrusaSlicer did not create G-code")
            gcode = output_path.read_bytes()
            if not gcode:
                raise SlicerExecutionError("PrusaSlicer created empty G-code")
            return gcode, {}
