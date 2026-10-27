"""Retained enclosure source and mechanical authority behavior (no hardware)."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/generate_sensor_retention_001.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _generator():
    spec = importlib.util.spec_from_file_location(
        "sensor_generator_fixture", ROOT / "scripts/generate_cross_domain_sensor_001.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_external_lid_ears_never_invent_board_holes(tmp_path):
    generation = _generator()
    generation.build_cross_domain_package(generation.sensor_only_spec(), tmp_path / "demo")
    mod = _load("retention_fixture")
    p = tmp_path / "demo"
    result = mod.create_retention(p)
    source = (p / "enclosure_retained.scad").read_text()
    assert "module retained_base()" in source
    assert "module retained_lid()" in source
    assert source.count("d=3.4") == 4
    assert result["nominal_added_volume_each_part_mm3"] > 250
    assert result["board_mounting"]["status"] == "BLOCKED_UNVERIFIED_BOARD_MOUNT_HOLES"
    assert not result["board_mounting"]["standoffs_generated"]
    assert result["expected_base_extent_mm"][0] > 70
    assert result["assembly_authorized"] is False
    assert result["fabrication_authorized"] is False
    with pytest.raises(FileExistsError):
        mod.create_retention(p)


def test_retention_refuses_mutated_source(tmp_path):
    generation = _generator()
    p = tmp_path / "demo"
    generation.build_cross_domain_package(generation.sensor_only_spec(), p)
    source = p / "enclosure.scad"
    source.write_text(source.read_text() + "// modified\n")
    with pytest.raises(ValueError, match="Untrusted source artifact"):
        _load("retention_fixture_mut").create_retention(p)


def test_retention_rejects_unbacked_fastener_geometry(tmp_path):
    generation = _generator()
    p = tmp_path / "demo"
    generation.build_cross_domain_package(generation.sensor_only_spec(), p)
    enc = p / "ENCLOSURE_INPUT.json"
    config = json.loads(enc.read_text())
    config["lid_mm"] = 0.5
    enc.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="Untrusted source artifact"):
        _load("retention_fixture_bad").create_retention(p)
