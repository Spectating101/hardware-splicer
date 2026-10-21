"""Adversarial printable casing constraints and actual independently audited STL."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from hardware_splicer.printed_enclosure_workbench import prepare_printed_enclosure
from scripts.run_printed_enclosure_workbench import _stl_report,_3mf_report,_close_bbox

ROOT=Path(__file__).resolve().parents[1]
SPEC=ROOT/"examples/printed_casing/conceptual_salvage_controller.json"
NATIVE=ROOT/"examples/printed_casing/native_trial"


@pytest.fixture
def concept():
    return json.loads(SPEC.read_text())


@pytest.fixture
def generated(concept):
    return prepare_printed_enclosure(concept)


def test_native_script_contains_hollow_shell_lid_port_bosses_and_vents(generated):
    commands=generated["solidcraft_print_layout_commands"]["commands"]
    names=[r["command"] for r in commands]
    assert names.count("solid.shell")==1
    assert names.count("plastic.boss")==8
    assert names.count("solid.box")==2
    assert names.count("solid.hole")==10
    assert names.count("solid.extrude")==2
    assert len(generated["lid_screw_centres_print_layout_xy_mm"])==4
    assert len(generated["lid_vent_centres_print_layout_xy_mm"])==6
    assert len(generated["sample_internal_board_mount_centres_mm"])==4
    assert any(r["params"].get("name")=="HS_Cable_Cutout" for r in commands)


def test_xy_clearance_is_per_side_and_lid_assembly_coordinates_align(generated):
    d=generated["case_dimensions_mm"]
    lid=generated["lid_alignment_mm"]
    assert [round(a-b,3) for a,b in zip(
        generated["cavity_dimensions_xy_mm"],lid["lip_outside_xy"],
    )]==[.7,.7]
    assert lid["nominal_xy_gap_per_side"]==.35
    xoff=generated["print_layout_mm"]["lid_offset_x"]
    D=d["depth"]
    centers=generated["lid_boss_centres_assembled_xy_mm"]
    print_holes=generated["lid_screw_centres_print_layout_xy_mm"]
    assert [[xoff+x,D-y] for x,y in centers] == [list(p) for p in print_holes]
    assert generated["solidcraft_assembly_transform"]["translate"]==[
        -xoff,D,d["base_height"]+d["lid_thickness"]
    ]


def test_parametric_casing_does_not_authorize_real_print(generated):
    for label in ("real_printer_connected","slicing_performed","printed",
                  "test_fitted","mechanical_production_release","physical_power_authorized"):
        assert generated[label] is False
    assert generated["source_confidence"].startswith("DECLARED_SOFTWARE_TEST")
    assert len(generated["unverified_fit_warnings"])>=5


@pytest.mark.parametrize("key,value",[
    ("outer_width",0),
    ("outer_depth",600),
    ("base_height",10),
    ("wall",0.3),
    ("lid_thickness",False),
    ("lip_thickness",0),
    ("lip_height",6),
    ("lip_clearance_per_side",0),
    ("lid_boss_outer_diameter",1),
    ("lid_boss_pilot_diameter",9.5),
    ("lid_boss_edge_offset",3),
    ("port_width",60),
    ("port_height",25),
    ("lid_vent_diameter",20),
    ("wall",float("nan")),
    ("base_height",float("inf")),
])
def test_bad_dimensions_cannot_generate_physical_candidate(concept,key,value):
    spec=copy.deepcopy(concept)
    spec["geometry_mm"][key]=value
    with pytest.raises(ValueError):
        prepare_printed_enclosure(spec)


def test_missing_or_fake_source_authority_rejected(concept):
    for value in (None,"MEASURED_SALVAGE","SELLER_PAGE","BENCH_VERIFIED"):
        altered=copy.deepcopy(concept)
        altered["evidence_type"]=value
        with pytest.raises(ValueError):
            prepare_printed_enclosure(altered)


def test_source_id_and_coordinates_change_deterministic_case_script(concept):
    a=prepare_printed_enclosure(concept)
    b=prepare_printed_enclosure(json.loads(json.dumps(concept)))
    assert a==b
    altered=copy.deepcopy(concept)
    altered["geometry_mm"]["outer_width"]=103
    c=prepare_printed_enclosure(altered)
    assert c["input_sha256"]!=a["input_sha256"]
    assert c["solidcraft_print_layout_commands"]!=a["solidcraft_print_layout_commands"]


def test_installed_real_generated_meshes_are_manifold_if_fixture_committed():
    # The committed native artifacts (once produced) are independent real
    # SolidCraft STL binary meshes, never hard-coded fake mesh statistics.
    if not (NATIVE/"HS_Casing_Base.stl").exists():
        pytest.skip("Native SolidCraft artifacts not committed yet")
    for name in ("Base","Lid"):
        report=_stl_report(NATIVE/f"HS_Casing_{name}.stl")
        assert report["closed_manifold"]
        assert report["triangles"]>100
        assert report["volume_mm3"]>1000
    assert _3mf_report(NATIVE/"CASE_PRINT_LAYOUT.3mf")["mesh_objects"]==2


def test_independent_bbox_checker_rejects_wrong_envelope():
    assert _close_bbox({"min":[0,0,0],"max":[100,75,35]},
                       [0,0,0],[100,75,35])
    assert not _close_bbox({"min":[0,0,0],"max":[101,75,35]},
                           [0,0,0],[100,75,35])


def test_sdk_exposes_guarded_print_casing_without_optional_mcp(concept):
    """The base HS SDK must work on core installs without the opt-in MCP SDK."""
    from hardware_splicer import sdk
    a=sdk.prepare_printed_casing(casing_spec=concept)
    assert a["real_printer_connected"] is False
    assert a["mechanical_production_release"] is False
    assert len(a["solidcraft_print_layout_commands"]["commands"]) >= 20


def test_optional_mcp_exposes_guarded_print_casing(concept):
    """Only require MCP when the optional SDK has actually been installed."""
    import asyncio
    pytest.importorskip("mcp.server", reason="opt-in HS MCP backend not installed")
    from hardware_splicer import sdk, mcp_server
    a=sdk.prepare_printed_casing(casing_spec=concept)
    tools=asyncio.run(mcp_server.list_tools())
    assert any(t.name=="hs_prepare_printed_casing" for t in tools)
    response=asyncio.run(mcp_server.call_tool(
        "hs_prepare_printed_casing",{"casing_spec":concept}
    ))
    b=json.loads(response[0].text)
    assert b["solidcraft_print_layout_commands"]==a["solidcraft_print_layout_commands"]
    assert b["mechanical_production_release"] is False


def test_modified_native_stl_geometry_is_detected(tmp_path):
    import struct
    src=NATIVE/"HS_Casing_Base.stl"
    data=bytearray(src.read_bytes())
    # Perturb only one real triangle vertex; it now has unmatched edges,
    # while binary STL size/count still appear perfectly valid.
    first_vertex=84+12
    old=struct.unpack_from("<f",data,first_vertex)[0]
    struct.pack_into("<f",data,first_vertex,old+0.6)
    tampered=tmp_path/"changed.stl"
    tampered.write_bytes(data)
    with pytest.raises(ValueError,match="non-manifold"):
        _stl_report(tampered)


def test_truncated_stl_binary_count_is_rejected(tmp_path):
    src=NATIVE/"HS_Casing_Lid.stl"
    tampered=tmp_path/"truncated.stl"
    tampered.write_bytes(src.read_bytes()[:-50])
    with pytest.raises(ValueError,match="count"):
        _stl_report(tampered)


def test_3mf_wrong_slicer_units_rejected(tmp_path):
    import zipfile
    original=NATIVE/"CASE_PRINT_LAYOUT.3mf"
    tampered=tmp_path/"mismatched_units.3mf"
    with zipfile.ZipFile(original) as inp,zipfile.ZipFile(tampered,"w") as out:
        for name in inp.namelist():
            contents=inp.read(name)
            if name.endswith(".model"):
                assert b'unit="millimeter"' in contents
                contents=contents.replace(b'unit="millimeter"',b'unit="inch"')
            out.writestr(name,contents)
    with pytest.raises(ValueError,match="unit"):
        _3mf_report(tampered)
