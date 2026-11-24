"""Small synthetic stand-in for a KiCad-derived investigator case.

Everything here is invented for tests. The pins, nets and counts are NOT
taken from any real board, and the commit and repository below do not exist.
The case manifest and reference snapshot are written to disk so the
production loader hashes real bytes, exactly as it would for a real case.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hardware_splicer.repair_investigator import REFNETS

CASE_FILE="case.json"
REFERENCE_FILE="synthetic_reference.json"
SCHEMATIC_FILE="synthetic_board.kicad_sch"
CAPTIONS_NAME="mkGEXlQ84wk.en-orig.vtt"


def synthetic_reference():
    extra=[f"/synthetic/NET{i}" for i in range(1,10)]
    names=list(REFNETS)+extra
    pins={"+5V":[("U7","6"),("U11","2"),("CN2","1")],
          "~{RESET}":[("U7","40"),("U12","3")],
          "PHI0":[("U7","1"),("U19","4")]}
    nets=[]
    for index,name in enumerate(names):
        pl=[{"ref":r,"pin":p} for r,p in pins.get(name,[("U7",str(10+index)),("U17",str(index+1))])]
        nets.append({"name":name,"pins":pl,"pin_count":len(pl)})
    refs=sorted({n["ref"] for net in nets for n in net["pins"]})
    return {
        "schema":"hs.circuit_kicad_reference_snapshot.v1",
        "synthetic_test_fixture":True,
        "board_design_id":"synthetic_board",
        "source_repository":"https://example.invalid/synthetic-board",
        "source_commit":"0123456789abcdef0123456789abcdef01234567",
        "source_license":"CERN-OHL-1.2",
        "source_files":{"250407_.kicad_sch":hashlib.sha256(b"synthetic").hexdigest()},
        "physical_target_revision_verified":False,
        "board_replica_not_identical_to_all_original_revisions":True,
        "kicad_export_warning":"synthetic fixture; annotation errors are simulated",
        "full_netlist_component_count":60,
        "full_netlist_net_count":60,
        "selected_nets":nets,
        "referenced_components":[{"ref":r} for r in refs],
    }


def write_case(directory:Path,captions:Path):
    """Write case.json and the reference snapshot next to each other."""
    directory.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(synthetic_reference(),sort_keys=True,indent=2)+"\n").encode()
    (directory/REFERENCE_FILE).write_bytes(raw)
    manifest={
        "schema":"hs.restoration.investigator_case.v1",
        "id":"synthetic_blank_board_case",
        "device":"Synthetic vintage computer board",
        "video_url":"https://www.youtube.com/watch?v=mkGEXlQ84wk",
        "video_title_symptom":"Synthetic nonworking board with missing ICs and previous repair work",
        "video_id":"mkGEXlQ84wk",
        "captions_filename":CAPTIONS_NAME,
        "video_auto_captions_sha256":hashlib.sha256(captions.read_bytes()).hexdigest(),
        "opening_cutoff_seconds":120,
        "inspection_cutoff_seconds":210,
        "source_reference_file":REFERENCE_FILE,
        "reference_snapshot_sha256":hashlib.sha256(raw).hexdigest(),
        "reference_board_photographed_and_independently_verified":False,
        "video_frames_analyzed":False,
        "hazards":["old_external_mains_power_adapter","vintage_electrolytic_capacitors"],
        "no_creator_outcome_in_inputs":True,
        "physical_repairs_authorized":False,
    }
    (directory/CASE_FILE).write_text(json.dumps(manifest))
    return directory/CASE_FILE
