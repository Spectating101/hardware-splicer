"""Offline file-conversion tests for HS CAD -> toolpath bridge."""
import hashlib
import subprocess
from pathlib import Path

import pytest

from hardware_splicer.manufacturing_operator.cad_pipeline import (
    render_openscad, slice_prusaslicer,
)
from hardware_splicer.manufacturing_operator.octoprint import ManufacturingRefusal


def _fake_binary(monkeypatch):
    monkeypatch.setattr("hardware_splicer.manufacturing_operator.cad_pipeline.shutil.which",
                        lambda name: "/mock/bin/" + name)


def test_render_scad_makes_mesh_receipt_not_fabrication_claim(tmp_path, monkeypatch):
    _fake_binary(monkeypatch)
    source = tmp_path / "part.scad"
    source.write_text("cube([10,10,10]);")
    target = tmp_path / "part.stl"
    def fake_run(command, **_kwargs):
        assert command[1] == "-o"
        Path(command[2]).write_bytes(b"solid mock\nendsolid mock\n")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
    monkeypatch.setattr("hardware_splicer.manufacturing_operator.cad_pipeline.subprocess.run",
                        fake_run)
    receipt = render_openscad(source, target)
    assert target.exists()
    assert receipt["stl_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert receipt["mesh_manifold_verified"] is False
    assert receipt["ready_for_print"] is False


def test_slicing_is_profile_bound_and_not_auto_authorized(tmp_path, monkeypatch):
    _fake_binary(monkeypatch)
    mesh = tmp_path / "part.stl"
    mesh.write_bytes(b"solid mock\nendsolid mock\n")
    profile = tmp_path / "trusted.ini"
    profile.write_text("layer_height = 0.2\n")
    target = tmp_path / "part.gcode"
    def fake_run(command, **_kwargs):
        assert "--export-gcode" in command and "--load" in command
        Path(command[command.index("--output") + 1]).write_text("; mock G-code\nG1 X1\n")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
    monkeypatch.setattr("hardware_splicer.manufacturing_operator.cad_pipeline.subprocess.run",
                        fake_run)
    with pytest.raises(ManufacturingRefusal, match="reviewed"):
        slice_prusaslicer(mesh, profile, target)
    assert not target.exists()
    result = slice_prusaslicer(mesh, profile, target, profile_reviewed_by_operator=True)
    assert result.profile_sha256 == hashlib.sha256(profile.read_bytes()).hexdigest()
    assert result.gcode_sha256 == hashlib.sha256(target.read_bytes()).hexdigest()
    assert not result.gcode_safety_verified
    assert not result.ready_for_auto_print


def test_invalid_input_and_overwrite_refused(tmp_path, monkeypatch):
    _fake_binary(monkeypatch)
    source = tmp_path / "missing.scad"
    with pytest.raises(ManufacturingRefusal):
        render_openscad(source, tmp_path / "x.stl")
    source.write_text("sphere(2);")
    target = tmp_path / "x.stl"
    target.write_bytes(b"existing")
    with pytest.raises(ManufacturingRefusal, match="overwrite"):
        render_openscad(source, target)
