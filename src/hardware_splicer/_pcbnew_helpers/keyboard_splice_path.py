"""Conservative grid-search cut-path proposal over a known KiCad board.

The scorer is not a fabrication planner. It penalizes loss of copper pads,
vias, and switch footprints; unknown/alternate footprints and true enclosure
geometry mean no path grants mechanical authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from shapely import points as shapely_points
from shapely import intersects, prepare, unary_union
from shapely.geometry import LineString, Point, box
from keyboard_splice_islands import _feature_geometries


def _geom_obstacles(board: dict):
    pads = []
    for row in board.get("pads", []):
        r = max(float(row.get("size_x_mm", 0)), float(row.get("size_y_mm", 0))) / 2
        if r>0:
            pads.append(Point(float(row["x"]),float(row["y"])).buffer(r+1.0,quad_segs=4))
    vias = []
    for row in board.get("vias", []):
        r = float(row.get("diameter_mm", 0))/2
        if r>0:
            vias.append(Point(float(row["x"]),float(row["y"])).buffer(r+1.0,quad_segs=6))
    switches = []
    for row in board.get("switch_positions", []):
        switches.append(Point(float(row["x"]),float(row["y"])).buffer(8.5,quad_segs=8))
    # Preserve controller, USB plug and crystals as no-cut structural keepouts.
    # It is safer to reject an unknown donor than to guess a tiny package.
    critical = []
    for row in board.get("footprints", []):
        ref = str(row.get("ref","")).upper()
        if ref.startswith(("IC","U","J","X")):
            critical.append(Point(float(row["x"]),float(row["y"])).buffer(11.0,quad_segs=8))
    return dict(pads=pads, vias=vias, switches=switches, critical=critical)


def _mask(points_arr, geometries):
    if not geometries:
        return np.zeros(len(points_arr),dtype=bool)
    aggregate=unary_union(geometries)
    return np.asarray(intersects(aggregate,points_arr),dtype=bool)


def _risk_counts(cut, objects):
    return {k:sum(g.intersects(cut) for g in v) for k,v in objects.items()}


def _x_at_y(path,y):
    y=float(y)
    for a,b in zip(path,path[1:]):
        if float(a[1])<=y<=float(b[1]):
            t=(y-float(a[1]))/max(float(b[1])-float(a[1]),1e-9)
            return float(a[0])+(float(b[0])-float(a[0]))*t
    return float(path[0][0] if y<float(path[0][1]) else path[-1][0])


def optimize_stepped_path(board: dict, *, step_mm: float=1.0, max_lateral_step_mm: float=3.0,
                          kerf_mm: float=1.0, allow_sacrificial_keys: bool=True,
                          x_fraction_min: float=.30, x_fraction_max: float=.70,
                          target_fraction: float=.50,
                          switch_penalty: float | None=None,
                          pad_penalty: float=20000.0):
    if not board.get("source_sha256"):
        raise ValueError("PCB source identity is missing")
    if step_mm<=0 or max_lateral_step_mm<=0 or kerf_mm<=0:
        raise ValueError("invalid physical cut parameters")
    if not (0.005 <= x_fraction_min < target_fraction < x_fraction_max <= 0.995):
        raise ValueError("invalid fractional cut search region")
    if pad_penalty <= 0 or (switch_penalty is not None and switch_penalty <= 0):
        raise ValueError("invalid cut loss penalties")
    b=board["outline_bbox_mm"]
    xmin,xmax=float(b["x_min"]),float(b["x_max"])
    ymin,ymax=float(b["y_min"]),float(b["y_max"])
    if min(xmax-xmin,ymax-ymin)<=0:
        raise ValueError("invalid board extent")
    xlo=xmin+x_fraction_min*(xmax-xmin); xhi=xmin+x_fraction_max*(xmax-xmin)
    nx=int(math.ceil((xhi-xlo)/step_mm))+1
    ny=int(math.ceil((ymax-ymin)/step_mm))+1
    if nx*ny>120000:
        raise ValueError("grid exceeds bounded topology study")
    xs=np.linspace(xlo,xhi,nx)
    ys=np.linspace(ymin,ymax,ny)
    coords=shapely_points(np.tile(xs,ny),np.repeat(ys,nx))
    obs=_geom_obstacles(board)
    # Grid stations are discrete, but the saw sweeps a continuous polygon.
    # Expand the scoring masks so a diagonal between two clear sample points
    # cannot graze the original critical-component envelope unnoticed.
    mask={k:_mask(coords, [g.buffer(1.75 if k=="critical" else 0.75) for g in v]).reshape(ny,nx)
          for k,v in obs.items()}
    # Unknown-controller geometry cannot be authoritatively cleared here.
    if not obs["critical"]:
        raise ValueError("no distinguishable controller/connector footprints")
    cost=np.zeros((ny,nx),dtype=float)
    cost+=mask["switches"]*(switch_penalty if switch_penalty is not None else (300 if allow_sacrificial_keys else 90000))
    cost+=(mask["pads"]|mask["vias"])*pad_penalty
    cost+=mask["critical"]*1000000
    # Tie break toward center to avoid a disingenuous extreme one-sided split.
    mid=xmin+(xmax-xmin)*target_fraction
    cost+=(np.abs(xs-mid)[None,:])*0.04
    prev=cost[0].copy()
    paths=np.full((ny,nx),-1,dtype=np.int32)
    radius=max(1,int(max_lateral_step_mm/step_mm)+1)
    for j in range(1,ny):
        new=np.full(nx,np.inf)
        for dx in range(-radius,radius+1):
            shift=np.arange(nx)-dx
            valid=(shift>=0)&(shift<nx)&(np.abs(xs-xs[np.clip(shift,0,nx-1)])<=max_lateral_step_mm*(ys[j]-ys[j-1])/step_mm+1e-9)
            valid_idx=np.flatnonzero(valid)
            if not len(valid_idx):continue
            scores=prev[shift[valid_idx]] + np.abs(xs[valid_idx]-xs[shift[valid_idx]])*0.4
            better=scores<new[valid_idx]
            indexes=valid_idx[better]
            new[indexes]=scores[better]
            paths[j,indexes]=shift[indexes]
        prev=new+cost[j]
    candidates=[]
    for last in np.argsort(prev)[:min(nx,80)]:
        if not np.isfinite(prev[last]): continue
        result=[]
        col=int(last)
        for j in range(ny-1,-1,-1):
            result.append((float(xs[col]),float(ys[j])))
            if j: col=int(paths[j,col])
            if col<0:break
        if len(result)!=ny:continue
        result.reverse()
        left=sum(float(s["x"])<_x_at_y(result,s["y"]) for s in board["switch_positions"])
        total=len(board["switch_positions"])
        balanced=bool(total) and min(left,total-left)/total>=.30
        # Avoid cuts which put 85% of key positions on one half.
        candidates.append((not balanced,float(prev[last]),result,left,total-left))
    if not candidates:
        raise ValueError("no path could be found across physical board")
    candidates.sort(key=lambda row:(row[0],row[1]))
    _, dp_cost, path, left,right=candidates[0]
    # Exact buffered polyline intersection is separately checked after DP's
    # discrete station sampling, catching gaps and diagonals.
    cut=LineString(path).buffer(kerf_mm/2,cap_style="flat",join_style="mitre")
    collisions=_risk_counts(cut,obs)
    physically_clear=all(v==0 for v in collisions.values())
    geometry_issues=set()
    inventory={str(t["net"]) for t in board.get("tracks",[]) if t.get("net")}
    inventory|={str(p["net"]) for p in board.get("pads",[]) if p.get("net")}
    inventory|={str(v["net"]) for v in board.get("vias",[]) if v.get("net")}
    inventory|={str(z["net"]) for z in board.get("filled_zones",[]) if z.get("net")}
    source_features=_feature_geometries(board,inventory,geometry_issues)
    affected_nets=sorted({f["net"] for f in source_features if f["geometry"].intersects(cut)})
    trimmed=[[round(x,4),round(y,4)] for x,y in path]
    result={
        "schema":"hs.keyboard-stepped-cut-solver.v1",
        "source_sha256":board["source_sha256"],
        "method":"deterministic monotone-grid DP + exact Shapely buffered path collision replay",
        "cut_points_mm":trimmed,
        "cut_path_type":"stepped_polyline",
        "kerf_mm":kerf_mm,
        "grid_step_mm":step_mm,
        "max_lateral_step_mm":max_lateral_step_mm,
        "objective_score":round(dp_cost,3),
        "search_parameters":{"x_fraction_min":x_fraction_min,"x_fraction_max":x_fraction_max,
                             "target_fraction":target_fraction,
                             "switch_penalty":switch_penalty if switch_penalty is not None else
                                (300 if allow_sacrificial_keys else 90000),
                             "pad_penalty":pad_penalty},
        "switch_candidates_left":left,"switch_candidates_right":right,
        "nominal_path_length_mm":round(float(LineString(trimmed).length),3),
        "collision_counts":collisions,
        "affected_nets":affected_nets,
        "affected_net_count":len(affected_nets),
        "source_geometry_issues":sorted(geometry_issues),
        "modeled_clear_of_listed_components":physically_clear,
        "source_footprints_may_have_alternative_layouts":True,
        "physical_cut_authorized":False,
        "release":"PROPOSED_CUT_ONLY_NOT_VERIFIED",
        "blockers":[
            "Actual installed switches, PCB stackup, case, plate and mounting keepouts not verified",
            "Pads modeled with conservative circles; nonrectangular pads and tilted footprints approximate",
            "Original PCB is a design reference, not a registered physical donor",
            "No mechanical or fabrication authority; physical cutting prohibited until independently reviewed",
        ]+([] if physically_clear else ["Proposed path intersects recorded copper pads, vias, switches or critical components"]),
    }
    s=json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    result["payload_sha256"]=hashlib.sha256(s.encode()).hexdigest()
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--board-json",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--no-sacrifice",action="store_true")
    args=ap.parse_args()
    b=json.loads(args.board_json.read_text(encoding="utf-8"))
    out=optimize_stepped_path(b,allow_sacrificial_keys=not args.no_sacrifice)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("STEPPED_PATH",len(out["cut_points_mm"]),"points",out["nominal_path_length_mm"],"mm")
    print("NOMINAL_OBSTACLE_COUNTS",out["collision_counts"])
    print("VERDICT",out["release"])

if __name__=="__main__":
    main()
