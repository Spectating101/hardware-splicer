"""Source-backed physical-interface test; geometry is NOT retention approval."""
from pathlib import Path
import importlib.util
import subprocess
import pytest
from hardware_splicer.engineering_kicad_interface import inspect_board_interface_bytes
from hardware_splicer.engineering_project_source_bundle import analyze_project_bundle


def test_non_kicad_board_source_is_rejected():
    result=inspect_board_interface_bytes(b'not an actual KiCad board')
    assert result['status']=='invalid_board_source'
    assert result['physical_fit_authorized'] is False


def test_real_reference_board_identifies_no_explicit_mounts():
    source=Path(__file__).resolve().parents[1]/'.cache/source-proofs/RPI_DEV_extracted/RPI Dev/RPI_Dev_1'
    pcb=source/'RPI_Dev_1.kicad_pcb'
    pro=source/'RPI_Dev_1.kicad_pro'
    sch=source/'RPI_Dev_1.kicad_sch'
    if not all(x.exists() for x in (pcb,pro,sch)):
        pytest.skip('upstream example board archive not restored in this test environment')
    result=analyze_project_bundle({x.name:x.read_bytes() for x in (pcb,pro,sch)})
    interface=result['board_interface_geometry']
    if interface['status']=='pcbnew_not_available':
        pytest.skip('KiCad Python extension absent from system interpreter')
    assert interface['status']=='extracted_kicad_source_geometry'
    assert interface['footprint_count']==26
    assert interface['explicit_mounting_footprint_refs']==[]
    assert interface['source_has_explicit_mounting_footprints'] is False
    assert interface['screw_retention_layout_resolved'] is False
    assert len(interface['nonplated_drill_features'])==1
    assert interface['nonplated_drill_features'][0]['reference']=='Q1'
    assert interface['nonplated_drill_features'][0]['drill_mm']=={'x':3.6,'y':3.6}
    assert interface['board_outline_aabb_mm']['width']==90.95
    assert interface['board_outline_aabb_mm']['height']==61.35
    assert interface['physical_fit_authorized'] is False
