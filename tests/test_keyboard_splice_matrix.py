"""Keypress functional check must require a fully closed source-bound matrix."""
from __future__ import annotations

import copy
import pytest

from hardware_splicer.keyboard_splice_matrix import verify_one_row_matrix


def facts():
    sha="a"*64
    pads=[]
    for i in range(6):
        pads.extend([
            {"net":"ROW_0","ref":f"SW{i+1}","pad":"1"},
            {"net":f"COL_{i}","ref":f"SW{i+1}","pad":"2"},
            {"net":f"COL_{i}","ref":"J1","pad":str(i+1)},
        ])
    pads.append({"net":"ROW_0","ref":"J1","pad":"7"})
    board={"source_sha256":sha,"source_label":"original_board.kicad_pcb","pads":pads}
    topo={"source_sha256":sha,"cut_path_sha256":"b"*64,
          "payload_sha256":"c"*64,"model_replay_remaining_required_components":0,
          "preexisting_unconnected_terminal_net_count":0,
          "damaged_electrical_pad_count":0}
    path={"source_sha256":sha,"payload_sha256":"b"*64,
          "collision_counts":{"pads":0,"vias":0,"switches":0,"critical":0}}
    drc={"kicad_version":"9.0.2","source":"original_board.kicad_pcb",
         "violations":[],"unconnected_items":[]}
    return board,topo,path,drc


def test_six_key_matrix_all_64_ideal_states():
    result=verify_one_row_matrix(*facts())
    assert result["keys"]==6
    assert result["ideal_switch_combinations_tested"]==64
    assert result["ideal_switch_combinations_failed"]==[]
    assert result["passive_keyboard_matrix_model_passed"] is True
    assert result["physical_controller_connected"] is False
    assert result["physical_repair_verified"] is False
    assert result["release"]=="SIMULATED_PASSIVE_MATRIX_ONLY"


@pytest.mark.parametrize("mutation", [
    "wrong_source","unclosed","source_baseline_gap","damaged_pad","cut_collision",
    "source_drc_error","wrong_header","duplicate_key_column",
])
def test_bad_matrix_or_uncertain_evidence_never_passes(mutation):
    b,t,p,d=facts()
    if mutation=="wrong_source":
        t["source_sha256"]="b"*64
    elif mutation=="unclosed":
        t["model_replay_remaining_required_components"]=1
    elif mutation=="source_baseline_gap":
        t["preexisting_unconnected_terminal_net_count"]=1
    elif mutation=="damaged_pad":
        t["damaged_electrical_pad_count"]=1
    elif mutation=="cut_collision":
        p["collision_counts"]["switches"]=1
    elif mutation=="source_drc_error":
        d["violations"]=[{"type":"unconnected_items"}]
    elif mutation=="wrong_header":
        d["source"]="another_board.kicad_pcb"
    else:
        for r in b["pads"]:
            if r["ref"]=="SW6" and r["pad"]=="2":
                r["net"]="COL_4"
    with pytest.raises(ValueError):
        verify_one_row_matrix(b,t,p,d)
