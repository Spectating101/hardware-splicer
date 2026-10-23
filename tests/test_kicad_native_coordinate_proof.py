"""Actual native KiCad UUID/coordinate proof and adversarial limits.

Run with real KiCad CLI + upstream converter, no hard-coded mapping.
The proof only concerns symbol center correlations on one source schematic.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hardware_splicer.integrations.kicad_native_coordinate_proof import prove_native_visual_positions

ROOT=Path(__file__).resolve().parents[1]
SCHEMATIC=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch"
SCRIPTS=ROOT/"examples/integrations/kicad-circuit-json"


@pytest.fixture(scope="module")
def sources(tmp_path_factory):
    if not shutil.which("kicad-cli") or not shutil.which("npm"):
        pytest.skip("Optional native KiCad and npm required")
    out=tmp_path_factory.mktemp("native-geometry")
    export=out/"official.net"
    converter=out/"converted.json"
    a=subprocess.run([
        "kicad-cli","sch","export","netlist","--format","kicadsexpr",
        "--output",str(export),str(SCHEMATIC)
    ],capture_output=True,text=True,timeout=100)
    assert a.returncode==0,a.stderr
    if not (SCRIPTS/"node_modules").is_dir():
        p=subprocess.run(["npm","install","--no-audit","--no-fund"],
                         cwd=SCRIPTS,capture_output=True,text=True,timeout=160)
        assert p.returncode==0,p.stderr
    b=subprocess.run(["npm","run","convert","--",str(SCHEMATIC),str(converter)],
                     cwd=SCRIPTS,capture_output=True,text=True,timeout=120)
    assert b.returncode==0,b.stderr
    return (SCHEMATIC.read_text(encoding="utf-8"),
            export.read_text(encoding="utf-8"),
            json.loads(converter.read_text(encoding="utf-8")),
            converter)


def prove(input_data):
    return prove_native_visual_positions(input_data[0],input_data[1],input_data[2])


def test_real_kiCad_position_proof_correlates_all_36_native_instances_and_79_pins(sources):
    r=prove(sources)
    assert r["native_component_count"]==36
    assert r["original_unique_metadata_anchors"]==21
    assert r["original_anchor_pins"]==52
    assert r["additional_coordinate_correlations"]==15
    assert r["source_position_correlated_instances"]==36
    assert r["source_position_correlated_pins"]==79
    assert r["geometry_positions_correlated"]
    assert r["unmatched_source_refs"]==[]
    assert abs(r["affine_frame"]["x_scale"]-1/15)<1e-12
    assert abs(r["affine_frame"]["y_scale"]+1/15)<1e-12
    assert abs(r["affine_frame"]["x_offset"]+7)<1e-12
    assert abs(r["affine_frame"]["y_offset"]-9.9)<1e-12
    assert max(item["coordinate_residual"] for item in r["correlations"])==0
    assert {m["kicad_ref"] for m in r["correlations"]} >= {"R2","R7","C3","TP17"}
    assert all(m["native_kicad_symbol_uuid"] and not m["direct_uuid_in_converter"] for m in r["correlations"])
    assert r["source_native_uuid_crosschecked_with_kicad_export"]
    assert not r["native_uuid_transmitted_by_converter"]
    assert not r["schematic_port_positions_validated"]
    assert not r["visual_electrical_geometry_merge_allowed"]


def test_shuffle_all_upstream_json_record_order_keeps_exact_position_correlations(sources):
    s,n,docs,_=sources
    a=prove_native_visual_positions(s,n,docs)
    b=prove_native_visual_positions(s,n,list(reversed(docs)))
    assert a["correlations"]==b["correlations"]
    assert a["affine_frame"]==b["affine_frame"]


def test_tamper_a_unique_anchor_position_breaks_coordinate_calibration(sources):
    s,n,docs,_=sources
    altered=copy.deepcopy(docs)
    c=next(x for x in altered if x["type"]=="source_component" and
           x["name"]=="HardwareSplicer:TXU0304PW")
    visual=next(x for x in altered if x["type"]=="schematic_component" and
                x["source_component_id"]==c["source_component_id"])
    visual["center"]["x"]+=1.0
    with pytest.raises(ValueError,match="anchors disagree"):
        prove_native_visual_positions(s,n,altered)


def test_alter_duplicate_resistor_position_with_valid_anchors_is_refused(sources):
    s,n,docs,_=sources
    altered=copy.deepcopy(docs)
    c=next(x for x in altered if x["type"]=="source_component" and
           x["source_component_id"]=="source_component_5")
    visual=next(x for x in altered if x["type"]=="schematic_component" and
                x["source_component_id"]==c["source_component_id"])
    visual["center"]["x"]+=0.2
    proof=prove_native_visual_positions(s,n,altered)
    assert proof["source_position_correlated_instances"]==35
    assert not proof["geometry_positions_correlated"]
    assert proof["unmatched_source_refs"]==["R2"]
    assert not proof["visual_electrical_geometry_merge_allowed"]


def test_tamper_native_symbol_uuid_disagrees_with_official_export_and_fails_closed(sources):
    s,n,docs,_=sources
    # Native schematic is the UUID authority, while official netlist export
    # independently carries the same symbol's instance/tstamp identity.
    import re
    mutated=s.replace("b5d5c85a-d95c-4484-b78f-e4b6b54fdda0",
                      "b5d5c85a-d95c-4484-b78f-e4b6b54fdda1",1)
    with pytest.raises(ValueError,match="UUID disagrees"):
        prove_native_visual_positions(mutated,n,docs)


def test_duplicate_identical_component_position_swap_shows_uuid_provenance_gap(sources):
    s,n,docs,_=sources
    original=prove_native_visual_positions(s,n,docs)
    altered=copy.deepcopy(docs)
    # R2 and R3 are both Device:R / 10k. Swapping their converter centers
    # cannot be detected using metadata+position alone: one-to-one native
    # UUID provenance MUST remain explicitly false.
    x=next(x for x in altered if x["type"]=="schematic_component" and
           x["source_component_id"]=="source_component_5")
    y=next(x for x in altered if x["type"]=="schematic_component" and
           x["source_component_id"]=="source_component_6")
    x["center"],y["center"]=y["center"],x["center"]
    secondary=prove_native_visual_positions(s,n,altered)
    assert secondary["source_position_correlated_instances"]==36
    orig={r["kicad_ref"]:r["converter_source_component_id"] for r in original["correlations"]}
    new={r["kicad_ref"]:r["converter_source_component_id"] for r in secondary["correlations"]}
    assert orig["R2"]!=new["R2"] and orig["R3"]!=new["R3"]
    assert not secondary["converter_record_provenance_authenticated"]
    assert not secondary["visual_electrical_geometry_merge_allowed"]


def test_real_cli_produces_audit_receipt_without_claiming_uuid_transport(sources,tmp_path):
    _,_,_,converter=sources
    output=tmp_path/"result.json"
    proc=subprocess.run([
        sys.executable,str(SCRIPTS/"prove_native_coordinates.py"),
        "--schematic",str(SCHEMATIC),"--converter-json",str(converter),
        "--out",str(output)
    ],check=True,capture_output=True,text=True,timeout=120)
    summary=json.loads(proc.stdout)
    assert summary["position_correlated"]==36
    assert summary["pin_number_correlated"]==79
    assert summary["additional_duplicate_type_position_matches"]==15
    assert summary["native_uuid_in_converter"] is False
    assert summary["visual_merge_allowed"] is False
    report=json.loads(output.read_text(encoding="utf-8"))
    assert len(report["correlations"])==36
