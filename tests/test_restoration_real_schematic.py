"""Real CC-BY-4.0 reverse-engineered KiCad source, not invented facts."""
from __future__ import annotations

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from hardware_splicer.restoration_schematic_grounding import (
    DATA, SCHEMATIC_MAIN, build_case_context, build_reference_tool_result,
    load_reference, source_connected_nets,
)
from hardware_splicer.restoration_reasoning_agent import (
    build_messages, sha, validate_model_output
)
from hardware_splicer.restoration_numeric_truth_gate import UnsupportedQuantitativeThreshold

ORIGINAL=Path("/tmp/hs-source-gb-schematics")

def ref():
    return build_reference_tool_result(reported_board_revision="DMG-CPU-06")

def test_actual_kicad_snapshot_with_authority_and_stable_source_hash():
    a,b=load_reference()
    assert a["commit"]=="032eb9c2578125b157ab88048113b2d52663b819"
    assert a["kicad_cli_version"]=="9.0.2"
    assert a["license"].startswith("CC-BY-4.0")
    assert b["reference_boards"]["DMG-CPU-06"]["component_count"]==50
    assert b["reference_boards"]["DMG-CPU-06"]["net_count"]==108
    assert b["reference_boards"]["DC-CONV-DMG-AB"]["component_count"]==19
    assert b["reference_boards"]["DC-CONV-DMG-AB"]["net_count"]==15

def test_real_board_source_has_noninvented_net_pins():
    x=ref()
    assert x["status"]=="reference_netlist_available_reported_revision_match_only"
    assert x["source_graph_claim_authority"]=="declared"
    assert x["target_board_physically_verified"] is False
    assert x["power_board_type_physically_verified"] is False
    assert x["converter_netlist_withheld_from_target_pin_inference"] is True
    observed={
        c["net"]:{(x["ref"],x["pin"]) for x in c["terminals"]}
        for c in x["candidate_battery_nets"]
    }
    assert {("BT1","1"),("DC1","4")}<=observed["/Power/BT+"]
    assert {("SW1","1"),("DC1","3"),("D1","1")}<=observed["/Power/SW1-VCC"]
    assert {("J1","4"),("SW1","2")}<=observed["VCC"]
    assert ("J1","1") in observed["VDD"]
    assert x["instrument_measurements_by_HS"] is False
    assert x["no_inferred_conduction_through_components"] is True
    assert x["repair_authorized"] is False

@pytest.mark.parametrize("reported",[
    None,"DMG-CPU-05","CGB-CPU-06","DMG-CPU-07","unknown",""
])
def test_revision_unknown_refuses_pin_specific_technical_claims(reported):
    x=build_reference_tool_result(reported_board_revision=reported)
    assert x["status"]=="board_revision_unmatched_pin_mapping_withheld"
    assert x["pin_specific_evidence_available"] is False
    assert x["candidate_battery_nets"]==[]
    assert x["target_board_physically_verified"] is False
    with pytest.raises(ValueError,match="unmatched schematic|reference board claim differs"):
        build_case_context(reported_board_revision=reported or "unknown",tool_reference=x)

def test_power_converter_board_subtype_must_not_be_silently_assumed():
    x=ref()
    assert "actual_power_converter_board_variant_not_confirmed" in x["unresolved_source_ids"]
    assert "no_verified_meter_observations" in x["unresolved_source_ids"]
    assert "board_revision_reported_by_website_not_verified_from_photo" in x["unresolved_source_ids"]

def test_same_evidence_for_control_and_real_artifact_assist():
    plain=build_case_context(reported_board_revision="DMG-CPU-06")
    hs=build_case_context(reported_board_revision="DMG-CPU-06",tool_reference=ref())
    assert hs["evidence"]==plain["evidence"]
    assert hs["evidence_sha256"]==plain["evidence_sha256"]
    assert hs["native_HS_repair_intake_schema"]=="hardware_splicer.repair_intake.v1"
    assert build_messages(plain)[1]==build_messages(hs)[1]
    assert build_messages(plain)[0]!=build_messages(hs)[0]
    assert "REAL_KICAD_SOURCE_JSON" in build_messages(hs)[0]["content"]
    assert "no converter-board subtype has been verified" in build_messages(hs)[0]["content"].lower()
    assert "creator_reported_result" not in json.dumps(build_messages(hs))
    assert sha(build_messages(plain))!=sha(build_messages(hs))

def test_reference_hash_tampering_blocks_inference(tmp_path):
    a=(DATA/"source_gb_dmg_manifest.json").read_bytes()
    b=json.loads((DATA/"dmg_netlist_snapshot.json").read_text())
    b["reference_boards"]["DMG-CPU-06"]["nets"][0]["nodes"][0]["pin"]="99"
    (tmp_path/"source_gb_dmg_manifest.json").write_bytes(a)
    (tmp_path/"dmg_netlist_snapshot.json").write_text(json.dumps(b))
    with pytest.raises(ValueError,match="hash mismatch"):
        load_reference(tmp_path)

def test_actual_source_checkout_files_match_fixed_hashes():
    if not ORIGINAL.exists():
        pytest.skip("pinned upstream source not available in CI")
    a,b=load_reference(source_checkout=ORIGINAL)
    assert len(a["files"])==5
    assert b["reference_boards"]["DMG-CPU-06"]["component_count"]==50

def test_real_kicad_cli_can_reexport_exact_referenced_electrical_nets(tmp_path):
    if not ORIGINAL.exists() or not shutil.which("kicad-cli"):
        pytest.skip("live pinned upstream KiCad checkout or KiCad CLI unavailable")
    target=tmp_path/"actual-export.xml"
    completed=subprocess.run([
        "kicad-cli","sch","export","netlist","--format","kicadxml",
        "-o",str(target),str(ORIGINAL/SCHEMATIC_MAIN),
    ],capture_output=True,text=True,timeout=45,check=False)
    assert completed.returncode==0,completed.stderr[:250]
    root=ET.parse(target).getroot()
    comps=root.findall("./components/comp")
    nets=root.findall("./nets/net")
    assert len(comps)==50
    assert len(nets)==108
    actual={n.get("name"):{
        (x.get("ref"),x.get("pin")) for x in n.findall("node")
    } for n in nets}
    assert {("BT1","1"),("DC1","4")}<=actual["/Power/BT+"]
    assert {("D1","1"),("DC1","3"),("SW1","1")}<=actual["/Power/SW1-VCC"]

def test_missing_components_do_not_fake_a_connection():
    snapshot=load_reference()[1]["reference_boards"]["DMG-CPU-06"]
    with pytest.raises(ValueError,match="absent from reference"):
        source_connected_nets(snapshot,{"FAKE999"})

def test_numeric_gate_still_blocks_unsupported_live_thresholds():
    context=build_case_context(reported_board_revision="DMG-CPU-06",tool_reference=ref())
    val={
        "summary":"Voltage not independently measured.",
        "hypotheses":[{
            "mechanism":"Suspected corroded battery contact",
            "why":"AA battery failure reported",
            "evidence_ids":["E1","E2"],
            "safe_test":"Check externally while unpowered"
        }],
        "next_safe_check":"Expect above 5.4V at power input for healthy unit.",
        "uncertainty":"Revision not independently verified.",
        "abstain":False,
    }
    with pytest.raises(UnsupportedQuantitativeThreshold):
        validate_model_output(val,context)
