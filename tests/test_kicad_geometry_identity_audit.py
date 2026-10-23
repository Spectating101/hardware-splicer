"""Strict source-to-visual identity checks, including adversarial ambiguity controls.

Only candidate geometry identities, NEVER automatic drawing/electrical merges.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hardware_splicer.integrations.kicad_geometry_identity_audit import audit_converter_geometry_identity

ROOT = Path(__file__).resolve().parents[1]
SCHEMATIC = ROOT / "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch"
SCRIPT = ROOT / "examples/integrations/kicad-circuit-json/audit_geometry_identity.py"


@pytest.fixture(scope="module")
def paired_sources(tmp_path_factory):
    if not shutil.which("kicad-cli") or not shutil.which("npm"):
        pytest.skip("Official KiCad and npm required to run actual upstream converter")
    work=tmp_path_factory.mktemp("geometry-audit")
    official=work/"official.net"
    converged=work/"converter.json"
    a=subprocess.run([
        "kicad-cli","sch","export","netlist","--format","kicadsexpr",
        "--output",str(official),str(SCHEMATIC),
    ],text=True,capture_output=True,timeout=100)
    assert a.returncode==0,a.stderr
    src=ROOT/"examples/integrations/kicad-circuit-json"
    if not (src/"node_modules").is_dir():
        p=subprocess.run(["npm","install","--no-audit","--no-fund"],
                         cwd=src,text=True,capture_output=True,timeout=160)
        assert p.returncode==0,p.stderr
    b=subprocess.run(["npm","run","convert","--",str(SCHEMATIC),str(converged)],
                     cwd=src,text=True,capture_output=True,timeout=120)
    assert b.returncode==0,b.stderr
    return official.read_text(),json.loads(converged.read_text()),converged


def _result(source,docs):
    return audit_converter_geometry_identity(source,docs)


def test_actual_upstream_converter_identifies_exactly_21_unique_visual_components_and_52_pins(paired_sources):
    net,docs,_=paired_sources
    report=_result(net,docs)
    assert report["source_component_count"]==36
    assert report["converter_source_component_count"]==40
    assert report["source_nets"]==19
    assert report["unique_candidate_matches"]==21
    assert report["matched_source_pin_numbers"]==52
    assert len(report["unmatched_kicad_references"])==15
    assert len(report["converter_only_component_ids"])==4
    assert {m["kicad_ref"] for m in report["candidate_matches"]} >= {"J1","JP1","U1","U2","U3","C2"}
    assert {"C1","C3","C4","C5","C6","R1","R2","R3","R4","R5","R6","R7","TP4","TP17","TP18"} == set(report["unmatched_kicad_references"])
    assert not report["visual_geometry_merged"]
    assert not report["electrical_connectivity_from_visual_traces_inferred"]
    assert not report["external_converter_component_identity_completely_verified"]
    assert not report["automatic_fabrication_authorized"]


def test_document_array_order_does_not_change_candidate_assignments(paired_sources):
    source,docs,_=paired_sources
    original=_result(source,docs)
    shuffled=_result(source,list(reversed(docs)))
    assert original["candidate_matches"]==shuffled["candidate_matches"]
    assert original["unmatched_kicad_references"]==shuffled["unmatched_kicad_references"]


def test_ambiguous_resistors_do_not_become_matched_when_geometry_is_reordered(paired_sources):
    source,docs,_=paired_sources
    altered=copy.deepcopy(docs)
    for item in altered:
        if item["type"]=="schematic_component":
            center=item.get("center") or {}
            center["x"]=999.0-float(center.get("x",0))
    result=_result(source,altered)
    assert len(result["candidate_matches"])==21
    assert "R2" in result["unmatched_kicad_references"]


def test_duplicate_unique_converter_symbol_forces_audit_abstention(paired_sources):
    source,docs,_=paired_sources
    altered=copy.deepcopy(docs)
    original=next(x for x in altered if x["type"]=="source_component"
                  and x["name"]=="HardwareSplicer:W25Q128JWS")
    extra={**original,"source_component_id":"spoof_extra_component"}
    altered.append(extra)
    report=_result(source,altered)
    assert "U2" in report["unmatched_kicad_references"]
    assert report["unique_candidate_matches"]==20
    assert "spoof_extra_component" in report["unmatched_converter_component_ids"]


def test_unexpected_source_pin_forces_abstention(paired_sources):
    source,docs,_=paired_sources
    altered=copy.deepcopy(docs)
    c=next(i for i in altered if i["type"]=="source_component"
           and i["name"]=="HardwareSplicer:TXU0304PW")
    p=next(i for i in altered if i["type"]=="source_port" and i["source_component_id"]==c["source_component_id"])
    p["pin_number"]=999
    report=_result(source,altered)
    assert "U1" in report["unmatched_kicad_references"]
    assert report["unique_candidate_matches"]==20
    assert any("pin_number_set_differs_from_kicad_source" in x["reason"] for x in report["refused_groups"])


def test_wrong_visual_port_parent_forces_abstention(paired_sources):
    source,docs,_=paired_sources
    altered=copy.deepcopy(docs)
    c=next(i for i in altered if i["type"]=="source_component"
           and i["name"]=="HardwareSplicer:W25Q128JWS")
    port=next(i for i in altered if i["type"]=="source_port" and i["source_component_id"]==c["source_component_id"])
    visual=next(i for i in altered if i["type"]=="schematic_port" and i["source_port_id"]==port["source_port_id"])
    visual["schematic_component_id"]="unknown_visual_parent"
    report=_result(source,altered)
    assert "U2" in report["unmatched_kicad_references"]
    assert report["unique_candidate_matches"]==20


def test_duplicate_port_id_is_a_hard_error_not_silent_overwrite(paired_sources):
    source,docs,_=paired_sources
    altered=copy.deepcopy(docs)
    src=next(i for i in altered if i["type"]=="source_port")
    altered.append(dict(src))
    with pytest.raises(ValueError,match="duplicate"):
        _result(source,altered)


def test_real_cli_audits_same_schematic_kicad_export_and_upstream_converter(paired_sources,tmp_path):
    source,docs,converter=paired_sources
    output=tmp_path/"audit.json"
    p=subprocess.run([
        sys.executable,str(SCRIPT),"--schematic",str(SCHEMATIC),
        "--converter-json",str(converter),"--out",str(output),
    ],capture_output=True,text=True,timeout=120,check=True)
    summary=json.loads(p.stdout)
    assert summary["candidate_matches"]==21
    assert summary["candidate_matched_pins"]==52
    assert summary["geometry_merged"] is False
    assert summary["source_uuid_confirmed"] is False
    report=json.loads(output.read_text())
    assert report["unique_candidate_matches"]==21
    assert report["source_schematic_sha256"]


def test_fails_without_actual_converter_documents():
    with pytest.raises(ValueError,match="array"):
        audit_converter_geometry_identity("(export (components) (nets))",{})
