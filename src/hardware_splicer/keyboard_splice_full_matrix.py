"""Trace original multi-row switch+diode+controller graph through an HS splice.

A source-bound ideal diode/switch scan model. This does not simulate firmware
timing, powered USB, exact source copper pours, mechanical assembly or any
physical donor. The original board must be independently DRC/bench checked.
"""
from __future__ import annotations

from collections import defaultdict, Counter
import hashlib
import itertools
import json
import random
import re


_ROW=re.compile(r"^/R(\d+)$")
_COL=re.compile(r"^/C(\d+)$")


def _receipt(value: dict) -> bool:
    original=value.get("payload_sha256")
    if not isinstance(original,str):
        return False
    data={k:v for k,v in value.items() if k!="payload_sha256"}
    encoded=json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(encoded.encode()).hexdigest()==original


def full_matrix_proof(
    source: dict, cut: dict, topology: dict, multi: dict,
    relocation: dict, relocation_verification: dict,
    bridge_manifest: dict, bridge_verification: dict,
    *, random_seed: int=20261116, random_cases: int=2048
) -> dict:
    """Check every original key/diode/controller channel & multiswitch patterns."""
    sha=source.get("source_sha256")
    if not isinstance(sha,str) or len(sha)!=64:
        raise ValueError("unidentified original PCB")
    if any(sha!=data.get(key) for data,key in (
        (cut,"source_sha256"),(topology,"source_sha256"),
        (multi,"source_sha256"),(relocation,"source_sha256"),
        (relocation_verification,"source_sha256"),
        (bridge_manifest,"source_reference_sha256"),
        (bridge_verification,"source_sha256"),
    )):
        raise ValueError("source SHA mismatch in assembled virtual design")
    if not _receipt(cut) or not _receipt(topology):
        raise ValueError("cut or topology receipt failed integrity check")
    choice=multi.get("selected_route",{})
    if choice.get("payload_sha256")!=cut["payload_sha256"]:
        raise ValueError("arbitrary-route optimizer altered the selected cut")
    if topology.get("cut_path_sha256")!=cut["payload_sha256"]:
        raise ValueError("original topology was computed for a different saw cut")
    if relocation.get("cut_path_sha256")!=cut["payload_sha256"]:
        raise ValueError("daughterboard wire map belongs to a different cut")
    if relocation.get("physical_authority_granted") is not False:
        raise ValueError("source remount attempted physical authorization")
    if (not relocation_verification.get("geometry_model_verified")
        or relocation_verification.get("drc_violations")!=0
        or relocation_verification.get("unconnected_items")!=0
        or not bridge_verification.get("native_design_checks_passed")
        or bridge_verification.get("native_drc_errors")!=0
        or bridge_verification.get("native_unconnected_items")!=0):
        raise ValueError("one or both generated KiCad PCBs fail native verification")
    if (topology.get("model_replay_remaining_required_components")!=0
        or topology.get("preexisting_unconnected_terminal_net_count")!=0
        or topology.get("damaged_electrical_pad_count")!=0):
        raise ValueError("original copper graph does not reconstruct the required nets")
    if not multi.get("selected_consequence",{}).get("nominally_salvageable_except_sacrificed_switches"):
        raise ValueError("material removal damages a required source PCB component")

    keys={str(row["ref"]):row for row in source.get("switch_positions",[])}
    if not 20<=len(keys)<=128:
        raise ValueError("untrusted full keyboard key population")
    pads=defaultdict(dict)
    for pad in source.get("pads",[]):
        ref=str(pad.get("ref",""))
        pin=str(pad.get("pad",""))
        net=str(pad.get("net",""))
        if not ref or not pin or not net:
            continue
        if pin in pads[ref] and pads[ref][pin]!=net:
            raise ValueError("duplicate source pad with incompatible net names")
        pads[ref][pin]=net

    controller=[(ref,p) for ref,p in pads.items()
                if any("Teensy" in str(row.get("footprint","")) and row.get("ref")==ref
                       for row in source.get("footprints",[]))]
    if len(controller)!=1:
        raise ValueError("expected one source-labeled controller footprint")
    controller_ref,controller_pins=controller[0]
    rows=sorted({name for name in controller_pins.values() if _ROW.fullmatch(name)},
                key=lambda name:int(_ROW.fullmatch(name).group(1)))
    cols=sorted({name for name in controller_pins.values() if _COL.fullmatch(name)},
                key=lambda name:int(_COL.fullmatch(name).group(1)))
    if not rows or not cols or len(rows)*len(cols)<len(keys):
        raise ValueError("controller does not expose enough matrix row and column nets")
    if rows!=[f"/R{i}" for i in range(len(rows))] or cols!=[f"/C{i}" for i in range(len(cols))]:
        raise ValueError("noncontiguous or ambiguous source matrix enumeration")
    controller_signal_pins=defaultdict(list)
    for pin,net in controller_pins.items():
        if net in rows or net in cols:
            controller_signal_pins[net].append(pin)
    if set(controller_signal_pins)!=set(rows+cols):
        raise ValueError("controller lacks one of the original row or column nets")
    if any(len(v)!=1 for v in controller_signal_pins.values()):
        raise ValueError("source controller signal is ambiguously connected to multiple pins")

    diodes=[(ref,p) for ref,p in pads.items() if ref.startswith("D") and p.get("1") and p.get("2")]
    by_anode=defaultdict(list)
    for ref,p in diodes:
        if p["1"] in rows:
            by_anode[p["2"]].append((ref,p["1"]))
    switch_routes=[]
    observed_pairs=set()
    diode_used=set()
    for ref in sorted(keys):
        keypads=pads.get(ref,{})
        if set(["1","2"]) - set(keypads):
            raise ValueError(f"missing required source key terminals {ref}")
        col=keypads["2"]
        link=keypads["1"]
        if col not in cols or not link:
            raise ValueError(f"unmapped controller-column or diode link on {ref}")
        paths=by_anode.get(link,[])
        if len(paths)!=1:
            raise ValueError(f"key {ref} lacks unique diode-to-matrix-row")
        diode,row=paths[0]
        if (row,col) in observed_pairs:
            raise ValueError("duplicate source row/column switch address")
        observed_pairs.add((row,col))
        if diode in diode_used:
            raise ValueError("multiple switches share one physical source diode")
        diode_used.add(diode)
        switch_routes.append({
            "ref":ref,"value":str(keys[ref].get("value","")),
            "source_switch_pad_1_net":link,
            "source_switch_pad_2_net":col,
            "diode_ref":diode,
            "diode_pad_2_net":link,
            "diode_pad_1_row_net":row,
            "row":row,"column":col,
            "controller_row_pin":controller_signal_pins[row][0],
            "controller_column_pin":controller_signal_pins[col][0],
        })
    if len(diode_used)!=len(keys):
        raise ValueError("some switch source diodes were not independently mapped")

    original_removed={str(r["ref"]) for r in multi["selected_consequence"]["sacrificed_switches"]}
    relocated={str(r["original_ref"]):r for r in relocation.get("source_wiring_map",[])}
    if original_removed!=set(relocated):
        raise ValueError("relocated key set differs from cut-removed switch set")
    if len(original_removed)!=relocation.get("key_switches_relocated"):
        raise ValueError("daughterboard switch count does not match lost keys")
    if len(keys)!=relocation.get("total_original_switch_positions_accounted"):
        raise ValueError("original keyboard key total is not conserved")
    if relocation.get("original_main_board_switches_retained")!=len(keys)-len(original_removed):
        raise ValueError("retained original physical-key accounting mismatch")

    daughter_channels=set()
    for entry in switch_routes:
        ref=entry["ref"]
        entry["recovered_by"]="daughterboard" if ref in relocated else "original_pcb"
        if ref not in relocated:
            continue
        target=relocated[ref]
        wiring=target.get("wire_map",[])
        if len(wiring)!=2:
            raise ValueError("source switch remount does not have exactly two conductors")
        originals=set()
        for wire in wiring:
            number=str(wire.get("original_source_pad",""))
            net=wire.get("original_source_net")
            if number not in ("1","2") or net!=pads[ref][number]:
                raise ValueError("relocation wire would connect wrong original source net")
            if target["source_pads"][number]["original_net"]!=net:
                raise ValueError("source original diode column net changed by remount")
            token=(str(wire.get("daughterboard_header_ref")),
                   str(wire.get("daughterboard_header_pad")))
            if token in daughter_channels:
                raise ValueError("two original key contacts share a daughterboard header pad")
            daughter_channels.add(token)
            originals.add(number)
            if wire.get("source_wire_connection_verified") is not False:
                raise ValueError("unmeasured physical wire incorrectly marked verified")
        if originals!={"1","2"}:
            raise ValueError("one of the removed switch contacts is not restored")
    if len(daughter_channels)!=2*len(relocated):
        raise ValueError("missing or shorted key remount connector assignment")

    original_bridge_edges=topology.get("bridge_edges",[])
    bridge_rows=bridge_manifest.get("channel_mapping",[])
    if len(original_bridge_edges)!=len(bridge_rows):
        raise ValueError("bridge does not include every modeled source-net restoration edge")
    original_island_edges={
        (r["net"],r["from_island"],r["to_island"]) for r in original_bridge_edges
    }
    bridged={
        (r["source_net"],r["from_model_island"],r["to_model_island"]) for r in bridge_rows
    }
    if len(original_island_edges)!=len(bridge_rows) or original_island_edges!=bridged:
        raise ValueError("interposer source island net mapping differs from topology")
    if bridge_manifest.get("physical_authority_granted") is not False:
        raise ValueError("interposer may not grant physical authority")

    # Source-specific diode polarity: in this reference source, pad 1 is the
    # shared-row diode cathode and pad 2 is the switch-side anode, i.e. current
    # from columns to selected (low-driven) row. We prove *topological* ghost
    # independence, not the electrical characteristics of its real diodes.
    items=[(r["row"],r["column"]) for r in switch_routes]
    indices_by_row=defaultdict(list)
    for i,(row,col) in enumerate(items):
        indices_by_row[row].append(i)

    number_patterns=0
    mismatch_examples=[]
    def scan(pressed):
        nonlocal number_patterns
        number_patterns+=1
        # Independent source expected net assignment: switch depressed = low
        # column while scanning its row.
        expected={row:{items[idx][1] for idx in pressed if items[idx][0]==row}
                  for row in rows}
        # Separate constructed directed-contact graph: anode-side column
        # connects through a closed switch and its diode to one row cathode.
        # Scan selects one row as a sink. Other rows remain high impedance.
        directed=defaultdict(set)
        for idx in pressed:
            row,col=items[idx]
            directed[col].add(row)
        observed={row:{col for col in cols if row in directed.get(col,set())}
                  for row in rows}
        if observed!=expected and len(mismatch_examples)<12:
            mismatch_examples.append({
                "pressed_refs":[switch_routes[i]["ref"] for i in pressed],
                "expected":{row:sorted(c) for row,c in expected.items()},
                "observed":{row:sorted(c) for row,c in observed.items()},
            })

    scan(())
    for i in range(len(items)):
        scan((i,))
    for pair in itertools.combinations(range(len(items)),2):
        scan(pair)
    for triple in itertools.combinations(range(len(items)),3):
        scan(triple)
    exhaustive_single_row_patterns=0
    for row in rows:
        indexes=indices_by_row[row]
        for mask in range(1<<len(indexes)):
            scan(tuple(indexes[j] for j in range(len(indexes)) if mask & (1<<j)))
            exhaustive_single_row_patterns+=1
    rng=random.Random(random_seed)
    for _ in range(random_cases):
        k=rng.randint(4,len(items))
        scan(tuple(sorted(rng.sample(range(len(items)),k))))

    result={
        "schema":"hs.source-bound-full-keyboard-matrix.v1",
        "source_sha256":sha,
        "cut_path_sha256":cut["payload_sha256"],
        "source_island_topology_sha256":topology["payload_sha256"],
        "original_controller_ref":controller_ref,
        "controller_row_to_pin":{row:controller_signal_pins[row][0] for row in rows},
        "controller_column_to_pin":{col:controller_signal_pins[col][0] for col in cols},
        "source_row_count":len(rows),
        "source_column_count":len(cols),
        "original_switch_count":len(items),
        "unique_switch_row_column_addresses":len(observed_pairs),
        "unique_source_diodes":len(diode_used),
        "retained_on_original_halves":len(items)-len(relocated),
        "relocated_to_addon_board":len(relocated),
        "daughterboard_source_wires":len(daughter_channels),
        "source_bound_interposer_channels":len(bridge_rows),
        "source_switch_diode_controller_map":switch_routes,
        "random_seed":random_seed,
        "random_multikey_patterns":random_cases,
        "single_key_patterns":len(items),
        "pair_patterns":len(items)*(len(items)-1)//2,
        "triple_patterns":len(items)*(len(items)-1)*(len(items)-2)//6,
        "all_one_row_subsets_tested":exhaustive_single_row_patterns,
        "total_ideal_press_patterns_tested":number_patterns,
        "mismatched_ideal_patterns":len(mismatch_examples),
        "failure_examples":mismatch_examples,
        "ideal_directed_diode_matrix_model_passed":not mismatch_examples,
        "diode_polarity_source_assumption":"row_pin_1_cathode_switch_pin_2_anode_unconfirmed_from_schematic",
        "source_native_kicad_drc_finished":False,
        "firmware_controller_pin_assignment_verified":False,
        "powered_USB_and_keyscan_tested":False,
        "real_62_key_conversion_assembled":False,
        "component_contact_physically_qualified":False,
        "released_for_fabrication":False,
        "verdict":"PASS_SOURCE_BOUND_IDEAL_MATRIX_ONLY" if not mismatch_examples else "FAIL_IDEAL_MATRIX",
    }
    blob=json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    result["payload_sha256"]=hashlib.sha256(blob.encode()).hexdigest()
    return result
