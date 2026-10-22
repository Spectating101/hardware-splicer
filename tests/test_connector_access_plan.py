"""Source-level connector clearance and net/pin identity for SPI enclosure.

These deterministic tests do not claim to have run native CAD or a physical fit.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.connector_access_plan import inspect_connector_access
from hardware_splicer.pcb_mounting_cad import generate_pcb_mounted_shell

ROOT=Path(__file__).resolve().parents[1]
PCB=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb"
SEED=ROOT/"examples/external_engines/cad/spi_adapter_shell.json"


def manifest(tmp_path, *, source=PCB):
    path=tmp_path/"mount.json"
    generate_pcb_mounted_shell(
        pcb_path=source,seed_recipe_path=SEED,
        output_recipe_path=tmp_path/"shell.json",
        output_manifest_path=path,
    )
    return path


def test_vertical_spi_headers_clear_nominal_open_top_cavity_and_bosses(tmp_path):
    source=manifest(tmp_path)
    result=inspect_connector_access(
        pcb_path=PCB,mounting_manifest_path=source,
        output_path=tmp_path/"connector_access.json",
    )
    assert result["status"]=="nominal_open_top_projection_clear_unverified",result
    assert result["connector_count"]==2
    assert {row["ref"] for row in result["connectors"]}=={"J1","JP1"}
    assert all(row["clear_of_cavity_walls_xy"] and row["clear_of_proposed_bosses_xy"]
               for row in result["connectors"])
    j1=next(x for x in result["connectors"] if x["ref"]=="J1")
    jp1=next(x for x in result["connectors"] if x["ref"]=="JP1")
    assert j1["cad_origin_xy_mm"]==[15,30]
    assert jp1["cad_origin_xy_mm"]==[57,48]
    assert len(j1["pcb_relative_pin_positions"])==6
    assert len(jp1["pcb_relative_pin_positions"])==2
    assert j1["nominal_open_top_space_above_board_mm"]==18.2
    assert not result["release_authorized"]
    assert not result["source_backed_manufacturer_mating_geometry"]
    stored=json.loads((tmp_path/"connector_access.json").read_text())
    assert stored==result


def test_larger_suggested_connector_mating_envelope_blocks_not_silently_passes(tmp_path):
    source=manifest(tmp_path)
    result=inspect_connector_access(pcb_path=PCB,mounting_manifest_path=source,
                                    side_margin_mm=10.0)
    assert result["status"]=="blocked_source_connector_courtyard_projection"
    assert any(not row["clear_of_proposed_bosses_xy"] for row in result["connectors"])


def test_mismatched_kicad_connector_and_mount_sources_are_rejected(tmp_path):
    source=manifest(tmp_path)
    altered=tmp_path/"altered.kicad_pcb"
    altered.write_bytes(PCB.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="source hashes disagree"):
        inspect_connector_access(pcb_path=altered,mounting_manifest_path=source)


def test_unbounded_connector_envelope_is_rejected(tmp_path):
    source=manifest(tmp_path)
    for invalid in (-1, 11, float("nan"), float("inf"), True):
        with pytest.raises(ValueError):
            inspect_connector_access(pcb_path=PCB,mounting_manifest_path=source,
                                     side_margin_mm=invalid)
