"""Verify true KiCad library pin locations versus real upstream converter ports.

Never conflate verified symbol pin positions with native converter UUID
provenance or authoritative wire/junction graph.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hardware_splicer.integrations.kicad_native_pin_geometry_audit import verify_native_pin_positions

ROOT=Path(__file__).resolve().parents[1]
SCHEMATIC=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch"
CONVERTER=ROOT/"examples/integrations/kicad-circuit-json"


def _require_external_tools():
    if not shutil.which("kicad-cli") or not shutil.which("npm"):
        pytest.skip("Requires official KiCad 9 CLI and real upstream converter")
    if not (CONVERTER/"node_modules").is_dir():
        result=subprocess.run(["npm","install","--no-audit","--no-fund"],
            cwd=CONVERTER,capture_output=True,text=True,timeout=160)
        assert result.returncode==0,result.stderr


def _run_real_pair(schematic:Path,tmp_path:Path):
    exported=tmp_path/(schematic.stem+".net")
    converted=tmp_path/(schematic.stem+".json")
    a=subprocess.run([
        "kicad-cli","sch","export","netlist","--format","kicadsexpr",
        "--output",str(exported),str(schematic)
    ],capture_output=True,text=True,timeout=100)
    assert a.returncode==0,a.stderr
    b=subprocess.run(["npm","run","convert","--",str(schematic),str(converted)],
        cwd=CONVERTER,capture_output=True,text=True,timeout=130)
    assert b.returncode==0,b.stderr
    return schematic.read_text(),exported.read_text(),json.loads(converted.read_text())


@pytest.fixture(scope="module")
def actual_input(tmp_path_factory):
    _require_external_tools()
    root=tmp_path_factory.mktemp("native-pin")
    return _run_real_pair(SCHEMATIC,root)


def _audit(x):
    return verify_native_pin_positions(*x)


def test_original_spi_flash_kicad_79_source_pin_centers_match_renderer(actual_input):
    result=_audit(actual_input)
    assert result["source_components"]==36
    assert result["component_centers_correlated"]==36
    assert result["source_numbered_pins"]==79
    assert result["source_library_pin_positions_verified"]==79
    assert result["failed_pin_or_component_checks"]==0
    assert result["all_pin_centers_correlated"]
    assert result["max_pin_position_residual"]==0
    assert result["observed_angle_degrees"]==[0]
    assert result["observed_mirror_axes"]==[""]
    assert not result["native_uuid_in_converter"]
    assert not result["visual_electrical_merge_allowed"]
    assert not result["schematic_junctions_wires_verified"]
    assert not result["physical_manufacturing_authorized"]


@pytest.mark.parametrize("variant,angle,mirror",[
    ("rotate90",90,None),("rotate180",180,None),("rotate270",270,None),
    ("mirrorX",0,"x"),("mirrorY",0,"y"),
    ("mirrorX90",90,"x"),("mirrorY90",90,"y")
])
def test_actual_upstream_converter_rotations_and_mirrors(
    actual_input,variant,angle,mirror,tmp_path
):
    source=actual_input[0]
    start=source.index('\n\t(symbol\n\t\t(lib_id "HardwareSplicer:TXU0304PW")')
    prefix,body=source[:start],source[start:]
    placement=f'(at 105.41 95.25 {angle})'
    if mirror:
        placement+=f'\n\t\t(mirror {mirror})'
    assert "(at 105.41 95.25 0)" in body
    modified=prefix+body.replace("(at 105.41 95.25 0)",placement,1)
    path=tmp_path/(variant+".kicad_sch")
    path.write_text(modified,encoding="utf-8")
    result=_audit(_run_real_pair(path,tmp_path))
    assert result["source_components"]==36
    assert result["source_numbered_pins"]==79
    assert result["source_library_pin_positions_verified"]==79
    assert result["failed_pin_or_component_checks"]==0
    assert result["all_pin_centers_correlated"]
    assert angle in result["observed_angle_degrees"]
    if mirror:
        assert mirror in result["observed_mirror_axes"]
    assert not result["visual_electrical_merge_allowed"]


def test_displaced_converted_port_cannot_pass_source_pin_geometry(actual_input):
    source,net,docs=actual_input
    altered=copy.deepcopy(docs)
    port=next(x for x in altered if x["type"]=="schematic_port")
    port["center"]["x"]+=0.14
    result=verify_native_pin_positions(source,net,altered)
    assert not result["all_pin_centers_correlated"]
    assert result["failed_pin_or_component_checks"]==1
    assert result["source_library_pin_positions_verified"]==78
    assert result["failed"][0]["reason"]=="converter_pin_center_differs_from_native_kicad"
    assert not result["visual_electrical_merge_allowed"]


def test_swapped_two_port_centers_on_same_component_are_detected(actual_input):
    source,net,docs=actual_input
    altered=copy.deepcopy(docs)
    comp=next(x for x in altered if x["type"]=="source_component"
              and x["name"]=="HardwareSplicer:TXU0304PW")
    pin_ids={x["source_port_id"] for x in altered if x["type"]=="source_port"
             and x["source_component_id"]==comp["source_component_id"]}
    records=[x for x in altered if x["type"]=="schematic_port"
             and x["source_port_id"] in pin_ids]
    assert len(records)>=2
    a,b=records[:2]
    a["center"],b["center"]=b["center"],a["center"]
    r=verify_native_pin_positions(source,net,altered)
    assert r["failed_pin_or_component_checks"]==2
    assert r["source_library_pin_positions_verified"]==77
    assert not r["all_pin_centers_correlated"]


def test_source_library_pin_tamper_is_detected_without_trusting_converter(actual_input):
    source,net,docs=actual_input
    key='''(pin power_in line'''
    # The native source embed can be altered while keeping source reference,
    # layout centers and official netlist UUIDs unchanged. It must fail.
    offset=source.index('(symbol "TXU0304PW_1_1"')
    before,tail=source[:offset],source[offset:]
    original='''(at -2.54 17.78 270)'''
    assert original in tail
    source_bad=before+tail.replace(original,'(at -2.54 20.32 270)',1)
    r=verify_native_pin_positions(source_bad,net,docs)
    assert not r["all_pin_centers_correlated"]
    assert any(v["reason"]=="converter_pin_center_differs_from_native_kicad" for v in r["failed"])


def test_swapping_visually_identical_complete_resistor_records_remains_provenance_unknown(actual_input):
    source,net,docs=actual_input
    original=_audit(actual_input)
    altered=copy.deepcopy(docs)
    p=[x for x in altered if x["type"]=="schematic_component"
       and x["source_component_id"] in {"source_component_5","source_component_6"}]
    assert len(p)==2
    p[0]["center"],p[1]["center"]=p[1]["center"],p[0]["center"]
    # Component centers alone still look plausible (as PR #212 found),
    # but moving the component without its ports yields mismatched pin
    # coordinates. If an attacker swaps *all* ports too, UUID provenance
    # is still unavailable from upstream.
    changed=verify_native_pin_positions(source,net,altered)
    assert changed["source_components"]==36
    assert not changed["native_uuid_in_converter"]
    assert not changed["visual_electrical_merge_allowed"]


def test_converter_document_order_cannot_change_pin_match_result(actual_input):
    source,net,docs=actual_input
    original=_audit(actual_input)
    reordered=verify_native_pin_positions(source,net,list(reversed(docs)))
    assert original["pin_correlations"]==reordered["pin_correlations"]
    assert original["all_pin_centers_correlated"]==reordered["all_pin_centers_correlated"]
