"""Bounded multi-strategy virtual cuts and explicit component-casualty accounting.

No physical process control is authorized. A "sacrificed switch" describes a
candidate removal from an *unverified reference footprint layout*, not a
completed PCB operation or a usable keymap.
"""
from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path

from shapely.geometry import LineString

from keyboard_splice_path import (
    _geom_obstacles, _x_at_y, optimize_stepped_path
)


STRATEGIES = (
    ("center-reuse", .30, .70, .50, 300.),
    ("center-protect-keys", .30, .70, .50, 90000.),
    ("left-reuse", .30, .70, .42, 300.),
    ("right-reuse", .30, .70, .58, 300.),
    ("left-protect-keys", .30, .70, .42, 15000.),
    ("right-protect-keys", .30, .70, .58, 15000.),
    ("extended-center", .20, .80, .50, 1200.),
    ("extended-left", .20, .80, .40, 1200.),
    ("extended-right", .20, .80, .60, 1200.),
    ("extended-protect-keys", .20, .80, .50, 75000.),
    ("wide-center", .10, .90, .50, 2500.),
    ("wide-protect-keys", .10, .90, .50, 90000.),
)


def audit_route(board: dict, route: dict) -> dict:
    if board.get("source_sha256") != route.get("source_sha256"):
        raise ValueError("cut path and donor source hashes differ")
    if route.get("release") != "PROPOSED_CUT_ONLY_NOT_VERIFIED":
        raise ValueError("unknown authority state")
    line = LineString(route["cut_points_mm"])
    corridor = line.buffer(float(route["kerf_mm"])/2,
                           cap_style="flat", join_style="mitre")
    obs = _geom_obstacles(board)
    signals=[]; mechanical=[]; vias=[]; switches=[]; critical=[]
    for i,geom in enumerate(obs["pads"]):
        if not geom.intersects(corridor):
            continue
        pad=board["pads"][i]
        sample={
            "ref":str(pad.get("ref","")), "pad":str(pad.get("pad","")),
            "net":str(pad.get("net","")),
            "pad_attribute":pad.get("pad_attribute"),
        }
        if pad.get("pad_attribute")==3:
            mechanical.append(sample)
        elif sample["net"]:
            signals.append(sample)
        else:
            # PTH mounting holes can be load-bearing even if unconnected.
            mechanical.append({**sample,"structural_mounting_hole":True})
    for kind,results,lookup in (
        ("vias",vias,board.get("vias",[])),
        ("switches",switches,board.get("switch_positions",[])),
        ("critical",critical,board.get("footprints",[])),
    ):
        for i,geom in enumerate(obs[kind]):
            if geom.intersects(corridor):
                ref=lookup[i]
                item={"ref":str(ref.get("ref",f"VIA:{i}")),
                      "x":float(ref.get("x",0)),
                      "y":float(ref.get("y",0))}
                if kind=="switches":
                    item["value"]=str(ref.get("value",""))
                    item["source_footprint"]=str(ref.get("footprint",""))
                results.append(item)
    sacrificed={item["ref"] for item in switches}
    removable_mechanical=[
        p for p in mechanical if p["pad_attribute"]==3 and p["ref"] in sacrificed
    ]
    unqualified_mechanical=[
        p for p in mechanical if p not in removable_mechanical
    ]
    kept=[s for s in board["switch_positions"] if s["ref"] not in sacrificed]
    left=sum(float(s["x"])<_x_at_y(route["cut_points_mm"],float(s["y"]))
             for s in kept)
    right=len(kept)-left
    fraction=min(left,right)/len(kept) if kept else 0
    balanced=fraction>=.30 and left>=2 and right>=2
    result={
        "schema":"hs.keyboard-cut-donor-consequence.v1",
        "source_sha256":route["source_sha256"],
        "cut_path_sha256":route["payload_sha256"],
        "total_reference_switch_candidates":len(board["switch_positions"]),
        "sacrificed_switches":sorted(switches,key=lambda x:x["ref"]),
        "sacrificed_key_count":len(sacrificed),
        "remaining_switches":len(kept),
        "remaining_left":left,
        "remaining_right":right,
        "remaining_split_balance_pass":balanced,
        "structural_or_electrically_unqualified_pad_hits":unqualified_mechanical,
        "nonplated_holes_inside_sacrificed_switches":removable_mechanical,
        "live_electrical_pad_hits":signals,
        "via_hits":vias,
        "critical_device_hits":critical,
        "reference_layout_assembly_verified":False,
        "source_donor_physical_identity_verified":False,
        "manufacturing_authority":False,
        "nominally_salvageable_except_sacrificed_switches":(
            balanced and not signals and not unqualified_mechanical
            and not vias and not critical
        ),
    }
    return result


def _rank(audit: dict, route: dict) -> tuple:
    # Balanced split is required, not merely low model collisions.
    return (
        0 if audit["remaining_split_balance_pass"] else 1,
        len(audit["critical_device_hits"]),
        len(audit["live_electrical_pad_hits"])+len(audit["via_hits"]),
        len(audit["structural_or_electrically_unqualified_pad_hits"]),
        audit["sacrificed_key_count"],
        len(audit["nonplated_holes_inside_sacrificed_switches"]),
        float(route["nominal_path_length_mm"]),
    )


def search_routes(board: dict, *, strategies=STRATEGIES) -> dict:
    if not board.get("switch_positions"):
        raise ValueError("at least two verified reference switch candidates required")
    records=[]
    seen=set()
    for name,lo,hi,target,weight in strategies:
        try:
            route=optimize_stepped_path(
                board, x_fraction_min=lo, x_fraction_max=hi,
                target_fraction=target, switch_penalty=weight
            )
            audit=audit_route(board,route)
            fingerprint=hashlib.sha256(json.dumps(route["cut_points_mm"],
                separators=(",",":")).encode()).hexdigest()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            records.append({
                "strategy":name,"route":route,"audit":audit,
                "rank":_rank(audit,route),
            })
        except ValueError as exc:
            records.append({"strategy":name,"rejected":str(exc)[:240]})
    feasible=[r for r in records if r.get("audit")]
    if not feasible:
        raise ValueError("all bounded automatic strategies failed to produce any cut")
    feasible.sort(key=lambda r:r["rank"])
    chosen=feasible[0]
    summaries=[]
    for row in records:
        if "audit" not in row:
            summaries.append({"strategy":row["strategy"],"status":"SEARCH_REJECTED",
                              "reason":row["rejected"]})
            continue
        a=row["audit"]
        summaries.append({
            "strategy":row["strategy"],
            "status":"PROPOSED_NOT_PHYSICALLY_AUTHORIZED",
            "source_sha256":row["route"]["source_sha256"],
            "cut_path_sha256":row["route"]["payload_sha256"],
            "candidate_losses":a["sacrificed_key_count"],
            "retained_keys":a["remaining_switches"],
            "remaining_left":a["remaining_left"],
            "remaining_right":a["remaining_right"],
            "balance_pass":a["remaining_split_balance_pass"],
            "live_pad_hits":len(a["live_electrical_pad_hits"]),
            "via_hits":len(a["via_hits"]),
            "unknown_mechanical_hits":len(a["structural_or_electrically_unqualified_pad_hits"]),
            "clean_of_essential_components_in_model":
                a["nominally_salvageable_except_sacrificed_switches"],
        })
    result={
        "schema":"hs.keyboard-multi-path-cut-recovery.v1",
        "source_sha256":board["source_sha256"],
        "attempted_strategies":len(strategies),
        "unique_proposed_paths":len(feasible),
        "selected_strategy":chosen["strategy"],
        "selected_route":chosen["route"],
        "selected_consequence":chosen["audit"],
        "candidate_summaries":summaries,
        "ranked_candidate_proposals":[{
            "strategy":row["strategy"],
            "route":row["route"],
            "consequence":row["audit"],
            "rank":list(row["rank"]),
        } for row in feasible[:5]],
        "any_remaining-key-balanced_route":any(
            r["audit"]["remaining_split_balance_pass"] for r in feasible
        ),
        "any_nominally_essential-component-clear_route":any(
            r["audit"]["nominally_salvageable_except_sacrificed_switches"]
            for r in feasible
        ),
        "physically_tested":False,
        "fabrication_authorized":False,
        "release":"BLOCKED_RESEARCH_ROUTE_ONLY",
    }
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--board-json",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--selected-cut-json",type=Path)
    args=ap.parse_args()
    board=json.loads(args.board_json.read_text(encoding="utf-8"))
    result=search_routes(board)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if args.selected_cut_json:
        args.selected_cut_json.parent.mkdir(parents=True,exist_ok=True)
        args.selected_cut_json.write_text(json.dumps(
            result["selected_route"],ensure_ascii=False,indent=2
        )+"\n",encoding="utf-8")
    consequence=result["selected_consequence"]
    print("MULTI_ROUTE",result["attempted_strategies"],"attempts",
          result["unique_proposed_paths"],"unique")
    print("SELECTED",result["selected_strategy"],"retained",
          consequence["remaining_switches"],"left/right",
          consequence["remaining_left"],consequence["remaining_right"],
          "sacrificed",consequence["sacrificed_key_count"])
    print("ELECTRICAL_PADS_DAMAGED",len(consequence["live_electrical_pad_hits"]))
    print("VIAS_DAMAGED",len(consequence["via_hits"]))
    print("UNQUALIFIED_MECHANICAL",len(
        consequence["structural_or_electrically_unqualified_pad_hits"]))
    print("RELEASE",result["release"])


if __name__=="__main__":
    main()
