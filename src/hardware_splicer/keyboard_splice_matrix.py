"""Passive one-row keyboard matrix regression on a source-bound virtual splice.

This verifies physical KiCad pad-to-net assignment and all 2^N ideal switch
closures. It does not model USB firmware, debounce, physical switch condition,
or any unmeasured real-world voltage/continuity behavior.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def verify_one_row_matrix(board: dict, topology: dict, path: dict,
                          source_native_drc: dict) -> dict:
    source=board.get("source_sha256")
    if not source or source!=topology.get("source_sha256") or source!=path.get("source_sha256"):
        raise ValueError("original physical PCB source identity mismatch")
    if topology.get("cut_path_sha256")!=path.get("payload_sha256"):
        raise ValueError("electrical reconstruction and material removal differ")
    if topology.get("model_replay_remaining_required_components")!=0:
        raise ValueError("required cut copper still disconnected")
    if topology.get("preexisting_unconnected_terminal_net_count")!=0:
        raise ValueError("original source terminal geometry is not closed")
    if topology.get("damaged_electrical_pad_count")!=0:
        raise ValueError("source copper component pad damaged")
    if any(v for v in path.get("collision_counts",{}).values()):
        raise ValueError("cut damages listed components")
    if source_native_drc.get("violations") or source_native_drc.get("unconnected_items"):
        raise ValueError("source native KiCad DRC is not clean")
    if not source_native_drc.get("kicad_version"):
        raise ValueError("unverified native KiCad checker")
    if source_native_drc.get("source") != board.get("source_label"):
        raise ValueError("source design and DRC report file identity differ")

    switches={}
    header={}
    for raw in board.get("pads",[]):
        ref=str(raw.get("ref",""))
        net=str(raw.get("net",""))
        number=str(raw.get("pad",""))
        if not net:
            continue
        if ref.startswith("SW") and ref[2:].isdigit() and number in ("1","2"):
            switches.setdefault(ref,{})[number]=net
        elif ref=="J1" and number.isdigit():
            header[int(number)]=net
    if not 2<=len(switches)<=12:
        raise ValueError("bounded 2-to-12-key single-row matrix required")
    if len(header)!=len(switches)+1:
        raise ValueError("controller header must have N column pins plus one row pin")
    if set(header)!=set(range(1,len(switches)+2)):
        raise ValueError("controller header pin indices are incomplete")
    names=[f"COL_{i}" for i in range(len(switches))]
    if [header[i+1] for i in range(len(switches))]!=names or header[len(switches)+1]!="ROW_0":
        raise ValueError("original controller header has wrong row/column nets")
    ordered=sorted(switches,key=lambda name:int(name[2:]))
    if ordered!=[f"SW{i+1}" for i in range(len(switches))]:
        raise ValueError("key switch positions are not uniquely indexed")
    for i,ref in enumerate(ordered):
        if switches[ref]!={"1":"ROW_0","2":f"COL_{i}"}:
            raise ValueError("switch source pads are not a one-row column matrix")
    count=1<<len(ordered)
    failures=[]
    for mask in range(count):
        # Ideal dry-switch model. Drive ROW_0 and observe a column only when
        # its unique MX contact is closed. One row prevents ghosting.
        energized={names[i] for i in range(len(ordered)) if mask & (1<<i)}
        observed=sum((1<<i) for i,name in enumerate(names) if name in energized)
        if observed!=mask:
            failures.append(mask)
    result={
        "schema":"hs.keyboard-single-row-matrix-proof.v1",
        "source_sha256":source,
        "topology_sha256":topology.get("payload_sha256"),
        "cut_path_sha256":path["payload_sha256"],
        "native_source_kicad_version":source_native_drc["kicad_version"],
        "row_net":"ROW_0",
        "column_nets":names,
        "key_switches":ordered,
        "keys":len(ordered),
        "ideal_switch_combinations_tested":count,
        "ideal_switch_combinations_failed":failures,
        "passive_keyboard_matrix_model_passed":not failures,
        "required_postcut_copper_groups_unresolved":0,
        "original_source_terminal_gap_count":0,
        "native_source_drc_violations":0,
        "physical_controller_connected":False,
        "firmware_loaded":False,
        "real_key_switches_tested":False,
        "physical_repair_verified":False,
        "release":"SIMULATED_PASSIVE_MATRIX_ONLY",
    }
    payload=json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    result["payload_sha256"]=hashlib.sha256(payload.encode()).hexdigest()
    return result
