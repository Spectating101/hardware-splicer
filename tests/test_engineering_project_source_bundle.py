"""No fake approvals: preserved source configuration is essential to KiCad validity."""
import hashlib
import struct
from pathlib import Path
import pytest

from hardware_splicer.engineering_project_source_bundle import (
    analyze_project_bundle, inspect_stl, analyze_registered_project_bundle,
)


def _minimal_binary_stl():
    head=bytes(80)+struct.pack('<I',1)
    tri=struct.pack('<12f',0,0,1,0,0,0,2,0,0,0,3,0)+b'\x00\x00'
    return head+tri


def test_real_binary_mesh_coordinates_are_unitless():
    r=inspect_stl(_minimal_binary_stl())
    assert r['triangle_count']==1
    assert r['axis_span']==[2.0,3.0,0.0]
    assert not r['fit_verified']
    assert r['units'].startswith('unresolved')


def test_board_without_project_refuses_equivalent_rule_check():
    r=analyze_project_bundle({'device.kicad_pcb':b'(kicad_pcb (version 2024))'})
    assert r['project_context']=='missing'
    assert r['software_checks']=={}
    assert not r['manufacturing_approved']


def test_bundle_never_trusts_client_supplied_hash():
    with pytest.raises(ValueError,match='hash mismatches'):
        analyze_project_bundle({'device.kicad_pcb':b'(kicad_pcb (version 2024))'},
                               source_identity={'device.kicad_pcb':'sha256:'+'0'*64})


def test_traversal_rejected():
    with pytest.raises(ValueError,match='safe basename'):
        analyze_project_bundle({'../dev.kicad_pcb':b'(kicad_pcb (version 2024))'})


def test_registered_project_fails_when_no_supported_sources(tmp_path):
    with pytest.raises(ValueError,match='no eligible'):
        analyze_registered_project_bundle('sample',[],project_root=tmp_path)


def test_actual_source_bundle_works_when_available():
    ref=Path('/tmp/hs-capability-trial-20261020/reference/extracted')
    names=['RPI_Dev_1.kicad_pro','RPI_Dev_1.kicad_sch','RPI_Dev_1.kicad_pcb','Front Case.stl']
    if not all((ref/name).is_file() for name in names):
        pytest.skip('real third-party trial source absent')
    import shutil
    if shutil.which('kicad-cli') is None:
        pytest.skip('KiCad CLI absent')
    r=analyze_project_bundle({name:(ref/name).read_bytes() for name in names})
    assert r['project_context']=='source_bundle_sibling_files_present'
    assert r['software_checks']['erc']['rule_finding_count']==43
    assert r['software_checks']['drc']['rule_finding_count']==16
    assert r['netlist']['component_count']==26
    assert r['netlist']['net_count']==47
    assert r['geometry']['Front Case.stl']['status']=='parsed_raw_bounds'
    assert not r['release_authorized']


def test_missing_companion_project_is_reported_without_kicad_cli(monkeypatch):
    """Source context errors must be stable in minimal/hosted CI environments."""
    from hardware_splicer import engineering_project_source_bundle as source_bundle
    monkeypatch.setattr(source_bundle.shutil, "which", lambda _: None)
    result = source_bundle.analyze_project_bundle({
        "missing_project.kicad_pcb": b"(kicad_pcb (version 2024))",
    })
    assert result["project_context"] == "missing"
    assert "companion .kicad_pro absent" in result["reason"]
    assert result["software_checks"] == {}
    assert not result["manufacturing_approved"]
