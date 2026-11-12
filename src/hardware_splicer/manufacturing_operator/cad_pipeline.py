"""Desktop CAD -> toolpath handoff using installed OpenSCAD and PrusaSlicer.

Only converts files; no printer operations and no assertion of manufacturability.
A trusted printer/material profile is required for slicing.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .octoprint import ManufacturingRefusal


@dataclass(frozen=True)
class ToolpathReceipt:
    mesh_sha256: str
    profile_sha256: str
    gcode_sha256: str
    gcode_path: str
    slicer: str
    operator_profile_reviewed: bool
    gcode_safety_verified: bool = False
    ready_for_auto_print: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _readable(path: Path, extension: str) -> Path:
    p = Path(path).resolve()
    if p.suffix.lower() != extension or not p.is_file() or p.stat().st_size <= 0:
        raise ManufacturingRefusal(f"Expected a non-empty {extension} input")
    return p


def render_openscad(source: Path, target_stl: Path, *, executable: str = "openscad") -> dict:
    source = _readable(source, ".scad")
    target = Path(target_stl).resolve()
    if target.suffix.lower() != ".stl":
        raise ManufacturingRefusal("OpenSCAD output must be .stl")
    binary = shutil.which(executable)
    if not binary:
        raise ManufacturingRefusal("OpenSCAD executable not installed")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ManufacturingRefusal("Refuse to overwrite existing STL")
    with tempfile.TemporaryDirectory(dir=target.parent, prefix="hs-scad-") as folder:
        intermediate = Path(folder) / "part.stl"
        try:
            process = subprocess.run([binary, "-o", str(intermediate), str(source)],
                                     capture_output=True, text=True, timeout=180, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ManufacturingRefusal(f"OpenSCAD could not complete: {type(exc).__name__}") from exc
        if process.returncode or not intermediate.is_file() or not intermediate.stat().st_size:
            raise ManufacturingRefusal("OpenSCAD did not produce a nonempty mesh")
        mesh_hash = hashlib.sha256(intermediate.read_bytes()).hexdigest()
        os.replace(intermediate, target)
    return {"stl_path": str(target), "stl_sha256": mesh_hash,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "mesh_manifold_verified": False, "ready_for_print": False}


def slice_prusaslicer(
    mesh_stl: Path, printer_profile_ini: Path, target_gcode: Path,
    *, executable: str = "prusa-slicer", profile_reviewed_by_operator: bool = False,
) -> ToolpathReceipt:
    mesh = _readable(mesh_stl, ".stl")
    profile = _readable(printer_profile_ini, ".ini")
    if not profile_reviewed_by_operator:
        raise ManufacturingRefusal("A locally reviewed printer/material profile is required")
    output = Path(target_gcode).resolve()
    if output.suffix.lower() != ".gcode":
        raise ManufacturingRefusal("Expected .gcode output")
    binary = shutil.which(executable)
    if not binary:
        raise ManufacturingRefusal("PrusaSlicer executable not installed")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ManufacturingRefusal("Refuse to overwrite existing G-code")
    mesh_hash = hashlib.sha256(mesh.read_bytes()).hexdigest()
    profile_hash = hashlib.sha256(profile.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(dir=output.parent, prefix="hs-slice-") as folder:
        intermediate = Path(folder) / "part.gcode"
        args = [binary, "--export-gcode", "--load", str(profile),
                "--output", str(intermediate), str(mesh)]
        try:
            process = subprocess.run(args, capture_output=True, text=True,
                                     timeout=300, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ManufacturingRefusal(f"PrusaSlicer could not complete: {type(exc).__name__}") from exc
        if process.returncode or not intermediate.is_file() or not intermediate.stat().st_size:
            raise ManufacturingRefusal("PrusaSlicer did not produce a nonempty G-code")
        if hashlib.sha256(mesh.read_bytes()).hexdigest() != mesh_hash or (
            hashlib.sha256(profile.read_bytes()).hexdigest() != profile_hash
        ):
            raise ManufacturingRefusal("Mesh or printer profile changed during slicing")
        code_hash = hashlib.sha256(intermediate.read_bytes()).hexdigest()
        os.replace(intermediate, output)
    return ToolpathReceipt(
        mesh_sha256=mesh_hash, profile_sha256=profile_hash,
        gcode_sha256=code_hash, gcode_path=str(output),
        slicer="PrusaSlicer CLI", operator_profile_reviewed=True,
    )
