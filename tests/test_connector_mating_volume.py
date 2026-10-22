"""Source-backed 3D connection service screen with explicit missing-harness block."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.connector_mating_volume import inspect_mating_volume
from hardware_splicer.pcb_mounting_cad import generate_pcb_mounted_shell

ROOT=Path(__file__).resolve().parents[1]
PCB=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb"
BOM=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/BOM.csv"
SEED=ROOT/"examples/external_engines/cad/spi_adapter_shell.json"


def make_manifest(tmp_path):
    path=tmp_path/"mounting.json"
    generate_pcb_mounted_shell(
        pcb_path=PCB,seed_recipe_path=SEED,
        output_recipe_path=tmp_path/"shell.json",output_manifest_path=path)
    return path


def test_real_samtec_headers_have_3d_sweeps_but_missing_mating_hardware_blocks(tmp_path):
    manifest=make_manifest(tmp_path)
    r=inspect_mating_volume(pcb_path=PCB,bom_path=BOM,
                            mounting_manifest_path=manifest,
                            output_path=tmp_path/"mating.json")
    assert r["status"]=="blocked_unqualified_mating_hardware_despite_nominal_3d_clearance",r
    assert r["examined_connector_count"]==2
    assert not r["nominal_geometry_blocked_references"],r
    assert not r["qualified_mating_geometry_verified"]
    for header in r["connectors"]:
        assert header["source_pcb_top_z_mm"]==6.8
        assert header["source_male_pin_tip_z_mm"]==15.18
        assert header["recess_from_shell_top_to_pin_tip_mm"]==9.82
        assert header["3d_insertion_sweep_aabb_mm"]["max_z"]==35
        assert header["nominal_3d_blockers"]==[]
        assert not header["mating_receptacle_wiring_solution_selected"]
        assert not header["cable_bend_radius_and_strain_relief_authenticated"]
    assert r["connectors"][1]["service_mode"]=="no_mate_for_jp1_initial_assembly"
    assert json.loads((tmp_path/"mating.json").read_text())==r


def test_wider_provisional_plug_blocks_instead_of_being_certified(tmp_path):
    path=make_manifest(tmp_path)
    r=inspect_mating_volume(pcb_path=PCB,bom_path=BOM,
                            mounting_manifest_path=path,radial_allowance_mm=12)
    assert r["status"]=="blocked_nominal_3d_insertion_geometry"
    assert r["nominal_geometry_blocked_references"]


def test_changed_male_header_part_identity_blocks(tmp_path):
    path=make_manifest(tmp_path)
    other=tmp_path/"BOM.csv"
    other.write_text(BOM.read_text().replace("TSW-106-07-T-S","FAKE-CONNECTOR"))
    with pytest.raises(ValueError,match="header MPN"):
        inspect_mating_volume(pcb_path=PCB,bom_path=other,
                             mounting_manifest_path=path)


def test_changed_mount_manifest_source_blocks(tmp_path):
    path=make_manifest(tmp_path)
    other=tmp_path/"bad.kicad_pcb"
    other.write_bytes(PCB.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="mount source"):
        inspect_mating_volume(pcb_path=other,bom_path=BOM,
                             mounting_manifest_path=path)


@pytest.mark.parametrize("invalid", [-0.1,12.5,float("nan"),float("inf"),True])
def test_invalid_insertion_allowances_block(tmp_path,invalid):
    path=make_manifest(tmp_path)
    with pytest.raises(ValueError):
        inspect_mating_volume(pcb_path=PCB,bom_path=BOM,
                             mounting_manifest_path=path,radial_allowance_mm=invalid)
