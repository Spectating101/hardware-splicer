"""Real KiCad mounting-hole source drives CAD instead of guessed positions."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import pytest
from hardware_splicer.pcb_mounting_cad import generate_pcb_mounted_shell

ROOT=Path(__file__).resolve().parents[1]
PCB=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb"
SHELL=ROOT/"examples/external_engines/cad/spi_adapter_shell.json"


def build(tmp_path, pcb=PCB, seed=SHELL):
    return generate_pcb_mounted_shell(
        pcb_path=pcb,seed_recipe_path=seed,
        output_recipe_path=tmp_path/"generated.json",
        output_manifest_path=tmp_path/"requirements.json")


def test_real_kicad_holes_generate_four_bosses_four_clearance_cuts(tmp_path):
    report=build(tmp_path)
    assert report["mount_count"]==4
    assert report["added_operations"]==8
    assert [a["ref"] for a in report["mounts"]]==["H1","H2","H3","H4"]
    assert sorted(tuple(a["cad_shell_center_xy_mm"]) for a in report["mounts"]) == [
        (14,14),(14,56),(96,14),(96,56)]
    assert not report["fabrication_authorized"]
    commands=json.loads((tmp_path/"generated.json").read_text())["commands"]
    assert len(commands)==16
    added=commands[8:]
    assert [x["params"]["operation"] for x in added]==["join","cut"]*4
    assert all(x["command"]=="solid.cylinder" for x in added)
    assert all(item["params"]["radius"]==3.3 for item in added[::2])
    assert all(item["params"]["radius"]==1.65 for item in added[1::2])
    raw=(tmp_path/"generated.json").read_bytes()
    assert "sha256:"+hashlib.sha256(raw).hexdigest()==report["generated_solidcraft_script_sha256"]


def test_frozen_boss_generator_is_deterministic(tmp_path):
    first=build(tmp_path)
    second=build(tmp_path)
    assert first==second


def test_tampered_board_hole_pattern_must_block(tmp_path):
    altered=tmp_path/"moved.kicad_pcb"
    source=PCB.read_text()
    assert "(at 104 64)" in source
    altered.write_text(source.replace("(at 104 64)","(at 103 64)",1))
    with pytest.raises(ValueError,match="pattern"):
        build(tmp_path,pcb=altered)


def test_altered_nominal_mount_diameter_is_rejected(tmp_path):
    altered=tmp_path/"different.kicad_pcb"
    source=PCB.read_text()
    assert "MountingHole:MountingHole_3.2mm_M3" in source
    altered.write_text(source.replace(
        "MountingHole:MountingHole_3.2mm_M3",
        "MountingHole:MountingHole_2.2mm_M2",1))
    with pytest.raises(ValueError,match="hole dimensions"):
        build(tmp_path,pcb=altered)


def test_different_shell_offset_requires_new_review(tmp_path):
    altered=tmp_path/"different_shell.json"
    source=json.loads(SHELL.read_text())
    source["commands"][4]["params"]["offset"]=3
    altered.write_text(json.dumps(source))
    with pytest.raises(ValueError,match="CAD seed dimensions"):
        build(tmp_path,seed=altered)
