"""Evidence-first virtual PCB cut/splice feasibility, never physical-cut authorization.

This is an engineering *screen* of a known KiCad design. It is not a valid
electrical reconstruction of an unknown recycled keyboard. Tracks are sampled
as planar copper segments; internal-layer geometry, zone connectivity, flex
membranes, enclosure interference, and physical solderability remain unresolved.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CutConfig:
    kerf_mm: float = 1.0
    pad_clearance_mm: float = 1.0
    switch_keepout_mm: float = 8.0
    min_key_side_fraction: float = 0.30
    scan_fraction_min: float = 0.30
    scan_fraction_max: float = 0.70
    scan_step_mm: float = 1.0


def _switch(f: dict[str, Any]) -> bool:
    ref = str(f.get("ref", ""))
    val = str(f.get("value", "")).lower()
    return ref.startswith("S") and (val.startswith("mx") or "switch" in val or "sw_push" in val)


def _kind(net: str) -> str:
    n = net.lower()
    if "/matrix/" in n or n.startswith("row") or n.startswith("col"):
        return "key_matrix"
    if "led" in n or "/leds/" in n or "rgb" in n or "backlight" in n:
        return "lighting_optional"
    if n in ("gnd", "vcc", "vbus", "3v3", "5v") or "power" in n:
        return "power_safety_review"
    return "other_unknown_do_not_discard"


def _dist_to_axis(x: float, seam: float) -> float:
    return abs(x-seam)


def _intersects_vertical_strip(track: dict[str, Any], x: float, half_width: float) -> bool:
    x1, x2 = float(track["x1"]), float(track["x2"])
    # Including tracks ending/starting within the kerf, and tracks lying
    # longitudinally under the kerf (which are also physically destroyed).
    return min(x1,x2) <= x+half_width and max(x1,x2) >= x-half_width


def _cut_one(board: dict[str, Any], x: float, cfg: CutConfig) -> dict[str, Any]:
    box = board["outline_bbox_mm"]
    half = cfg.kerf_mm/2
    crossings = [t for t in board["tracks"] if _intersects_vertical_strip(t,x,half)]
    segments_per_net = Counter(t["net"] for t in crossings if t.get("net"))
    intersected_nets = sorted(segments_per_net)
    kinds = Counter(_kind(n) for n in intersected_nets)
    pads = [
        p for p in board["pads"]
        if _dist_to_axis(float(p["x"]),x) <= half + cfg.pad_clearance_mm
        + max(float(p.get("size_x_mm", 0)),float(p.get("size_y_mm",0)))/2
    ]
    vias = [
        v for v in board.get("vias",[])
        if _dist_to_axis(float(v["x"]),x) <= half+cfg.pad_clearance_mm+float(v.get("diameter_mm",0))/2
    ]
    # Switch plate/keycap dimensions are unknown. 8mm is an explicit
    # conservative switch-center keepout, NOT footprint-verified clearance.
    switches = board["switch_positions"]
    key_centers_intersected = [s for s in switches if _dist_to_axis(float(s["x"]),x) <= half+cfg.switch_keepout_mm]
    left = sum(1 for s in switches if float(s["x"]) < x)
    right = len(switches)-left
    balanced = len(switches)>0 and min(left,right)/len(switches)>=cfg.min_key_side_fraction
    # Candidate endpoints are from pads only, not arbitrary exposed trace. A
    # pad near a net doesn't prove that it survives the saw or can be soldered.
    pad_by_net: dict[str,list[dict]] = defaultdict(list)
    for p in board["pads"]:
        if p.get("net") in segments_per_net:
            pad_by_net[p["net"]].append(p)
    harness=[]
    for net in intersected_nets:
        pp=pad_by_net.get(net,[])
        def endpoint(side: str) -> dict[str,Any] | None:
            candidates=[p for p in pp if
                (float(p["x"]) < x-half-cfg.pad_clearance_mm if side=="left"
                 else float(p["x"]) > x+half+cfg.pad_clearance_mm)]
            if not candidates: return None
            c=min(candidates,key=lambda p:abs(float(p["x"])-x))
            return {k:c[k] for k in ("ref","pad","x","y","layer","net") if k in c}
        harness.append({
            "net":net,
            "function_class":_kind(net),
            "crossed_segments":segments_per_net[net],
            "left_candidate_pad":endpoint("left"),
            "right_candidate_pad":endpoint("right"),
            "connection_required": "unresolved_requires_board_topology_and_continuity",
        })
    return {
        "x_mm":round(x,3),
        "track_segments_touched":len(crossings),
        "distinct_nets_touched":len(intersected_nets),
        "net_categories":dict(sorted(kinds.items())),
        "matrix_nets_touched":sorted(n for n in intersected_nets if _kind(n)=="key_matrix"),
        "pads_at_risk":len(pads),
        "vias_at_risk":len(vias),
        "switch_centers_at_risk":len(key_centers_intersected),
        "switch_candidates_left":left,
        "switch_candidates_right":right,
        "key_balance_pass":balanced,
        "valid_straight_seam":balanced and not pads and not vias and not key_centers_intersected,
        "all_intersected_nets":intersected_nets,
        "harness_candidates":harness,
    }


def evaluate_cut(board: dict[str, Any], *, cfg: CutConfig = CutConfig(), requested_x_mm: float | None = None) -> dict[str, Any]:
    """Scan physically conservative vertical seams and fail closed."""
    b=board["outline_bbox_mm"]
    xmin=float(b["x_min"]); xmax=float(b["x_max"])
    if xmax <= xmin: raise ValueError("board outline has zero or negative width")
    if cfg.kerf_mm<=0 or cfg.scan_step_mm<=0: raise ValueError("invalid tool width or scan step")
    if not board.get("tracks") or not board.get("pads"):
        raise ValueError("PCB requires real copper tracks and pads, not a generic mock")
    if not board.get("source_sha256"):
        raise ValueError("PCB requires source hash before analysis")
    center=(xmin+xmax)/2
    start=xmin+(xmax-xmin)*cfg.scan_fraction_min
    stop=xmin+(xmax-xmin)*cfg.scan_fraction_max
    steps=int((stop-start)/cfg.scan_step_mm)+1
    if steps>5000: raise ValueError("scan would exceed conservative step budget")
    candidates=[_cut_one(board,start+i*cfg.scan_step_mm,cfg) for i in range(steps)]
    candidates.sort(key=lambda c:(
        0 if c["valid_straight_seam"] else 1,
        0 if c["key_balance_pass"] else 1,
        c["switch_centers_at_risk"],c["pads_at_risk"],c["vias_at_risk"],
        len(c["matrix_nets_touched"]),c["distinct_nets_touched"],
        c["track_segments_touched"],abs(c["x_mm"]-center)
    ))
    best=candidates[0]
    midpoint=_cut_one(board,center,cfg)
    requested=_cut_one(board,requested_x_mm,cfg) if requested_x_mm is not None else None
    incomplete_pad_mapping=sum(1 for c in best["harness_candidates"] if
        c["left_candidate_pad"] is None or c["right_candidate_pad"] is None)
    blockers=[
        "No evidence that a physical donor PCB matches this reference PCB revision",
        "Copper planes, actual connected paths, and multi-crossing net topology are not proven by segment intersections",
        "Cut-edge tolerances, component/plate keepouts and case/fastener clearances need physical registration",
        "Candidate pad locations are not checked for solderability or post-cut continuity",
        "Firmware matrix behavior, original controller, USB, ESD and safety require a physical test",
        "No authority to cut, solder, fabricate or sell hardware from this design scan"
    ]
    if not any(x["valid_straight_seam"] for x in candidates):
        blockers.insert(0,"NO SAFE STRAIGHT SEAM found under conservative footprint/pad/via keepout")
    if incomplete_pad_mapping:
        blockers.append(f"{incomplete_pad_mapping} crossed nets lack a pad on one or both sides")
    if board.get("zone_count",0):
        blockers.append(f"{board['zone_count']} copper zone objects need fill/return-path validation after cutting")
    if board.get("source_warnings"):
        blockers.append("PCB source import reported source warnings; see evidence")
    return {
        "schema":"hs.keyboard-cut-splice-screen.v1",
        "source_file_sha256":board["source_sha256"],
        "source_label":board.get("source_label","external PCB reference"),
        "source_design_only":True,
        "physical_donor_exists":False,
        "analysis_tool":"Native KiCad pcbnew geometry extraction + HS bounded geometry screen",
        "config":vars(cfg),
        "board":{k:board[k] for k in ("outline_bbox_mm","zone_count") if k in board},
        "counts":{"tracks":len(board["tracks"]),"pads":len(board["pads"]),"via_count":len(board.get("vias",[])),"switch_footprint_candidates":len(board["switch_positions"])},
        "scanned_straight_seams":len(candidates),
        "passing_seams":sum(x["valid_straight_seam"] for x in candidates),
        "midpoint":{k:v for k,v in midpoint.items() if k!="harness_candidates"},
        "best_scanned_straight_seam":best,
        "requested_seam":requested,
        "release":"BLOCKED_REFERENCE_ONLY",
        "next_action":"Identify one exact-model salvaged keyboard; obtain both PCB images and unpowered continuity; identify controller/optional circuits; design stepped cut and interposer based on real measurements",
        "blockers":blockers
    }


def write_report(result: dict[str,Any], json_path: Path) -> None:
    json_path.parent.mkdir(parents=True,exist_ok=True)
    json_path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
