"""Source-derived keyboard harness integrates the bridge and remounted keys.

A DRC-clean 20-net bus is a research assembly fixture, NOT a physically
qualified connector/harness or real e-waste restoration.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_remount_round5"
GENERATOR=ROOT/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_harness_bus.py"
NATIVE="/usr/bin/python3"


def native_available():
    if not shutil.which("kicad-cli"):
        return False
    try:
        test=subprocess.run([NATIVE,"-c","import pcbnew"],capture_output=True,timeout=9)
        return test.returncode==0
    except (OSError,subprocess.TimeoutExpired):
        return False


pytestmark=pytest.mark.skipif(not native_available(),reason="requires actual KiCad pcbnew and kicad-cli")


FILES=[
    "F60_MATRIX_SOURCE_SLICE.json",
    "POSTCUT_ISLANDS.json",
    "interposer/INTERPOSER_CHANNEL_MAP.json",
    "key_remount/RELOCATION_MAP.json",
    "FULL_MATRIX_SOURCE_PROOF.json",
    "INDEPENDENT_SOURCE_AUDIT.json",
]


def data():
    return [json.loads((FROZEN/name).read_text(encoding="utf-8")) for name in FILES]


def run_native(tmp_path,records):
    paths=[]
    for i,record in enumerate(records):
        target=tmp_path/(f"source_{i}.json")
        target.write_text(json.dumps(record),encoding="utf-8")
        paths.append(target)
    out=tmp_path/"junction"
    command=[NATIVE,str(GENERATOR)]
    for key,p in zip((
        "--source-json","--topology-json","--bridge-json",
        "--remount-json","--matrix-json","--source-audit-json"
    ),paths):
        command.extend([key,str(p)])
    command.extend(["--out",str(out)])
    p=subprocess.run(command,capture_output=True,text=True,timeout=30)
    return p,out


def test_actual_kicad_junction_one_terminal_per_unique_donor_pad(tmp_path):
    result,out=run_native(tmp_path,data())
    assert result.returncode==0,result.stderr
    manifest=json.loads((out/"FULL_JUNCTION_WIRING.json").read_text(encoding="utf-8"))
    assert manifest["source_original_pads_with_only_one_wire_each"]==39
    assert manifest["relocated_key_header_pins"]==10
    assert manifest["total_junction_board_pins"]==49
    assert manifest["unique_source_nets_joined"]==20
    assert manifest["original_bridge_edges_replaced"]==17
    assert manifest["separate_original_bridge_interposer_should_not_be_installed_in_parallel"] is True
    assert manifest["physical_assembly_authorized"] is False
    assert manifest["actual_harness_connector_mpn"] is None
    assert manifest["fabrication_release"]=="BLOCKED_SOURCE_REFERENCE_JUNCTION_PREVIEW"

    contacts=manifest["source_terminal_mapping"]
    assert len(contacts)==49
    original=[(r["source_ref"],r["source_pin"]) for r in contacts if r["external_role"]=="donor"]
    addon=[(r["source_ref"],r["source_pin"]) for r in contacts if r["external_role"]=="remount"]
    assert len(original)==len(set(original))==39
    assert len(addon)==len(set(addon))==10
    assert len({r["original_source_net"] for r in contacts})==20
    assert all(not r["physical_wire_installed"] for r in contacts)
    assert all(not r["physical_mating_verified"] for r in contacts)
    c5=[r for r in contacts if r["original_source_net"]=="/C5"]
    assert len(c5)==7
    assert len({r["harness_net"] for r in c5})==1

    pcb=out/"keyboard_recovery_junction.kicad_pcb"
    checked=subprocess.run([
        "kicad-cli","pcb","drc","--format","json",
        "--output",str(out/"NATIVE_DRC.json"),str(pcb)
    ],capture_output=True,text=True,timeout=60)
    assert checked.returncode==0,checked.stderr
    drc=json.loads((out/"NATIVE_DRC.json").read_text(encoding="utf-8"))
    assert not drc.get("violations")
    assert not drc.get("unconnected_items")
    probe=subprocess.run([NATIVE,"-c",(
        "import pcbnew as p,json,sys;"
        "b=p.LoadBoard(sys.argv[1]);"
        "print(json.dumps({'footprints':len(b.GetFootprints()),"
        "'tracks':len(b.GetTracks()),"
        "'pads':sum(len(list(f.Pads())) for f in b.GetFootprints())}))"
    ),str(pcb)],capture_output=True,text=True,timeout=30)
    assert probe.returncode==0,probe.stderr
    counts=json.loads(probe.stdout)
    assert counts=={"footprints":20,"tracks":29,"pads":49}


@pytest.mark.parametrize("damage",[
    "pcb_sha","cut_receipt","source_net_wiring","source_pad_number",
    "multiple_source_nets","incomplete_copper","bridge_mismatch",
    "relocation_duplicate_port","incomplete_matrix","schematic_mismatch",
])
def test_untrusted_or_incomplete_harness_inputs_refuse_generation(tmp_path,damage):
    records=copy.deepcopy(data())
    src,top,bridge,remount,proof,audit=records
    if damage=="pcb_sha":
        src["source_sha256"]="f"*64
    elif damage=="cut_receipt":
        top["payload_sha256"]="0"*64
    elif damage=="source_net_wiring":
        bridge["channel_mapping"][0]["source_net"]="unrelated_net"
    elif damage=="source_pad_number":
        bridge["channel_mapping"][0]["from_candidate_contact"]["pad"]="BAD"
    elif damage=="multiple_source_nets":
        for part in remount["source_wiring_map"]:
            if part["original_ref"]=="K15":
                part["wire_map"][0]["original_source_net"]="/C5"
                break
    elif damage=="incomplete_copper":
        top["model_replay_remaining_required_components"]=3
    elif damage=="bridge_mismatch":
        bridge["topology_sha256"]="f"*64
    elif damage=="relocation_duplicate_port":
        remount["source_wiring_map"][1]["wire_map"][0]["daughterboard_header_ref"]=(
            remount["source_wiring_map"][0]["wire_map"][0]["daughterboard_header_ref"])
    elif damage=="incomplete_matrix":
        proof["ideal_directed_diode_matrix_model_passed"]=False
    elif damage=="schematic_mismatch":
        audit["net_assignment_equivalence"]=False
    process,_=run_native(tmp_path,records)
    assert process.returncode!=0
