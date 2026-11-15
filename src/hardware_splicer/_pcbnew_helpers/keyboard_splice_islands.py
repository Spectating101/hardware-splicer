"""Copper-island cut simulator with source-bounded partial connectivity.

Executed by the system Python hosting shapely. This is a conservative
*reference-model* simulation: no physical release or manufacturing authorization.
Zone pour, arc geometry, flex circuits, layer stacks beyond F/B, and missing
board revision are always unresolved. No assumptions about thermal/ESD pathways.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import json
from pathlib import Path

from shapely import make_valid
from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
from keyboard_splice_repair import recover_contacts, classify_inert_cut_remnant

LAYERS = ("F.Cu", "B.Cu")


class DisjointSet:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int):
        a, b = self.find(x), self.find(y)
        if a == b:
            return
        if self.rank[a] < self.rank[b]:
            a, b = b, a
        self.parent[b] = a
        if self.rank[a] == self.rank[b]:
            self.rank[a] += 1


def _polygon_parts(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    if hasattr(g, "geoms"):
        out = []
        for geom in g.geoms:
            out.extend(_polygon_parts(geom))
        return out
    return []


def _feature_geometries(board: dict, target_nets: set[str], issues: set[str]) -> list[dict]:
    features = []

    def add(net, layer, geom, kind, ident, pad=None, physical_id=None):
        if not net or net not in target_nets:
            return
        if layer not in LAYERS:
            issues.add("UNSUPPORTED_COPPER_LAYER")
            return
        features.append({
            "net": net, "layer": layer, "geometry": geom,
            "kind": kind, "id": ident, "pad": pad,
            "physical_id": physical_id if physical_id is not None else ident,
        })

    for i, track in enumerate(board.get("tracks", [])):
        net = track.get("net")
        if net not in target_nets:
            continue
        layer = str(track.get("layer", ""))
        width = track.get("width_mm")
        if not isinstance(width, (int, float)) or width <= 0:
            issues.add("TRACK_WIDTH_MISSING")
            continue
        start = (float(track["x1"]), float(track["y1"]))
        end = (float(track["x2"]), float(track["y2"]))
        shape = LineString([start, end]).buffer(float(width) / 2, resolution=4)
        if not shape.is_empty:
            add(net, layer, shape, "track", f"track:{i}")

    for i, pad in enumerate(board.get("pads", [])):
        net = pad.get("net")
        if net not in target_nets:
            continue
        attr = pad.get("pad_attribute")
        shape = pad.get("pad_shape")
        if attr is None or shape is None:
            issues.add("PAD_GEOMETRY_METADATA_MISSING")
            continue
        # KiCad PAD_ATTRIB_PTH=0, SMD=1, NPTH=3.
        if attr == 3:
            continue
        if attr not in (0, 1):
            issues.add("PAD_TYPE_UNSUPPORTED")
            continue
        x, y = float(pad["x"]), float(pad["y"])
        w = float(pad["size_x_mm"])
        h = float(pad["size_y_mm"])
        if w <= 0 or h <= 0:
            issues.add("PAD_SIZE_MISSING")
            continue
        if shape == 0 and abs(w - h) < 0.01:  # circular
            poly = Point(x, y).buffer(w / 2, resolution=16)
        elif shape == 1:  # rectangular
            poly = box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
            poly = rotate(poly, -float(pad.get("orientation_degrees", 0)), origin=(x, y))
        elif shape == 2:  # oval; use bounding rectangle: conservative approximation flagged
            issues.add("OVAL_PAD_APPROXIMATION")
            poly = box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
            poly = rotate(poly, -float(pad.get("orientation_degrees", 0)), origin=(x, y))
        else:
            # custom, trapezoid etc; cannot silently synthesize geometry
            issues.add(f"PAD_SHAPE_UNSUPPORTED:{shape}")
            continue
        physical_id = f"pad:{i}"
        solder = {"ref": pad.get("ref", ""), "pad": pad.get("pad", ""),
                  "x": x, "y": y, "net": net, "layer": pad.get("layer", "")}
        if attr == 0:
            for layer in LAYERS:  # plated through-hole barrel assumed continuous when intact
                add(net, layer, poly, "pad", f"pad:{i}:{layer}", solder, physical_id)
        else:
            add(net, pad.get("layer"), poly, "pad", f"pad:{i}", solder, physical_id)

    for i, via in enumerate(board.get("vias", [])):
        net = via.get("net")
        if net not in target_nets:
            continue
        if str(via.get("via_type", "3")) != "3":  # legacy KiCad through via; verify if this changes
            issues.add("VIA_TYPE_UNVERIFIED")
        radius = float(via.get("diameter_mm", 0)) / 2
        if radius <= 0:
            issues.add("VIA_DIAMETER_MISSING")
            continue
        physical_id = f"via:{i}"
        for layer in LAYERS:
            add(net, layer, Point(float(via["x"]), float(via["y"])).buffer(radius, resolution=12),
                "via", f"via:{i}:{layer}", physical_id=physical_id)
    # Respect KiCad's *filled* copper polygons, not just the zone outlines
    # (a fill has thermal spokes, clearance cutouts and disconnected islands).
    # Rule areas and keepouts are not conducting copper and are never added.
    if "filled_zones" not in board:
        if board.get("zone_count",0):
            issues.add("UNMODELED_COPPER_ZONES")
    else:
        for zone_index, zone in enumerate(board["filled_zones"]):
            if zone.get("net") not in target_nets:
                continue
            if not zone.get("is_filled"):
                issues.add("RELEVANT_COPPER_ZONE_UNFILLED")
                continue
            polygons=zone.get("polygons", [])
            if not polygons:
                issues.add("RELEVANT_COPPER_ZONE_MISSING_GEOMETRY")
                continue
            for poly_index, data in enumerate(polygons):
                poly=Polygon(data["shell"],data.get("holes", []))
                if poly.is_empty:
                    issues.add("RELEVANT_COPPER_ZONE_EMPTY_POLYGON")
                    continue
                if not poly.is_valid:
                    # KiCad 9 may read legacy touch/self-intersection zone
                    # boundaries. GEOS make_valid keeps the polygonal areas
                    # while preserving a blocker for ambiguous zero-width
                    # contacts and edges.
                    poly=make_valid(poly)
                    issues.add("ZONE_BOUNDARY_RECONSTRUCTED_WITH_GEOMETRY_REPAIR")
                converted=_polygon_parts(poly)
                if not converted:
                    issues.add("RELEVANT_COPPER_ZONE_UNUSABLE")
                for part_index, piece in enumerate(converted):
                    add(zone["net"],zone["layer"],piece,"zone",
                        f"zone:{zone_index}:{poly_index}:{part_index}")
    return features


def _seam_x_at_y(path: list[list[float]] | None, y: float, default_x: float) -> float:
    if path is None:
        return default_x
    if y <= float(path[0][1]):
        return float(path[0][0])
    if y >= float(path[-1][1]):
        return float(path[-1][0])
    for (x1,y1),(x2,y2) in zip(path,path[1:]):
        if float(y1) <= y <= float(y2):
            t=(y-float(y1))/(float(y2)-float(y1))
            return float(x1)+(float(x2)-float(x1))*t
    raise ValueError("cut path does not span target y")


def _fragments(features: list[dict], cut_x: float | None, kerf_mm: float,
               *, cut_shape=None, stepped_path=None) -> list[dict]:
    kerf = cut_shape if cut_shape is not None else (
        box(cut_x - kerf_mm / 2, -1e8, cut_x + kerf_mm / 2, 1e8) if cut_x is not None else None
    )
    out = []
    for feature in features:
        polys = [feature["geometry"]] if kerf is None else _polygon_parts(feature["geometry"].difference(kerf))
        for j, poly in enumerate(polys):
            f = {k: v for k, v in feature.items() if k != "geometry"}
            f["geometry"] = poly
            f["origin_id"] = feature["id"]
            x_at_y = _seam_x_at_y(stepped_path,float(poly.centroid.y),float(cut_x or 0))
            f["side"] = "full" if kerf is None else ("left" if poly.centroid.x < x_at_y else "right")
            f["fragment_id"] = (feature["id"], j)
            # A partly sawn-through pad is not a reliable solder endpoint.
            f["intact_pad"] = (
                feature["kind"] == "pad" and
                (kerf is None or feature["geometry"].disjoint(kerf))
            )
            out.append(f)
    return out


def _connect(fragments: list[dict]) -> DisjointSet:
    ds = DisjointSet(len(fragments))
    grouped = defaultdict(list)
    for i, f in enumerate(fragments):
        grouped[(f["net"], f["layer"])].append(i)
    for idxs in grouped.values():
        geoms = [fragments[i]["geometry"] for i in idxs]
        tree = STRtree(geoms)
        for j, geom in enumerate(geoms):
            for local in tree.query(geom, predicate="intersects"):
                k = int(local)
                if k > j:
                    ds.union(idxs[j], idxs[k])
    # plated through-hole pads and via barrels bridge F/B only if physically
    # within the same intact post-cut copper island. For damaged barrel pads/vias
    # unioning fragments on the same side is still conservative about continuity,
    # but *any* cut-touching hole is separately blocked as a mechanical hazard.
    bridges = defaultdict(list)
    for i, f in enumerate(fragments):
        if f["kind"] in ("pad", "via"):
            bridges[(f["physical_id"], f["side"])].append(i)
    for idxs in bridges.values():
        for i in idxs[1:]:
            ds.union(idxs[0], i)
    return ds


def _islands(fragments, ds):
    grouped = defaultdict(list)
    for i, f in enumerate(fragments):
        grouped[(f["net"], ds.find(i))].append(i)
    return grouped


def _pad_candidates(fragments, component_idxs: list[int], seam: float, stepped_path=None) -> list[dict]:
    pads = {}
    for idx in component_idxs:
        f = fragments[idx]
        if f["kind"] != "pad" or not f["intact_pad"]:
            continue
        p = f["pad"]
        key = (p["ref"], p["pad"], p["x"], p["y"])
        pads[key] = p
    return sorted(pads.values(), key=lambda p: (abs(float(p["x"]) - _seam_x_at_y(stepped_path,float(p["y"]),seam)), str(p["ref"]), str(p["pad"])))[:4]


def simulate_islands(board: dict, cut_x_mm: float, kerf_mm: float = 1.0,
                     target_nets: list[str] | None = None, cut_path: dict | None = None,
                     repair_mode: str = "pad_only") -> dict:
    if not board.get("source_sha256"):
        raise ValueError("missing source digest")
    if repair_mode not in ("pad_only", "adaptive", "adaptive_functional"):
        raise ValueError("unsupported copper island repair mode")
    if kerf_mm <= 0:
        raise ValueError("kerf must be positive")
    xmin = float(board["outline_bbox_mm"]["x_min"])
    xmax = float(board["outline_bbox_mm"]["x_max"])
    if not xmin < cut_x_mm < xmax:
        raise ValueError("cut must pass through the documented board extent")
    stepped_path=None
    cut_shape=None
    path_digest=None
    if cut_path is not None:
        digest=cut_path.get("payload_sha256")
        body={k:v for k,v in cut_path.items() if k!="payload_sha256"}
        actual=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False,
                                         separators=(",",":")).encode()).hexdigest()
        if not digest or actual != digest:
            raise ValueError("cut path receipt digest invalid")
        if cut_path.get("source_sha256") != board["source_sha256"]:
            raise ValueError("cut path revision does not match PCB")
        if cut_path.get("release") != "PROPOSED_CUT_ONLY_NOT_VERIFIED":
            raise ValueError("cut path authority state unsupported")
        if abs(float(cut_path.get("kerf_mm",0))-kerf_mm)>1e-9:
            raise ValueError("topology and path kerf differ")
        stepped_path=cut_path.get("cut_points_mm",[])
        b=board["outline_bbox_mm"]
        if (len(stepped_path)<2 or
            abs(float(stepped_path[0][1])-float(b["y_min"]))>.05 or
            abs(float(stepped_path[-1][1])-float(b["y_max"]))>.05):
            raise ValueError("path endpoints must span board")
        if any(not xmin<float(p[0])<xmax for p in stepped_path):
            raise ValueError("path has point outside PCB x bounds")
        if any(not float(a[1])<float(c[1]) for a,c in zip(stepped_path,stepped_path[1:])):
            raise ValueError("path y points must be monotone")
        cut_shape=LineString(stepped_path).buffer(kerf_mm/2,cap_style="flat",join_style="mitre")
        path_digest=digest
    if target_nets is None:
        raise ValueError("explicit target-net inventory required")
    requested = set(target_nets)
    if not requested or "" in requested:
        raise ValueError("target nets must be nonempty and named")
    issues = set()
    if board.get("copper_layer_count", 2) != 2:
        issues.add("MULTILAYER_PCB_UNSUPPORTED")
    if board.get("source_warnings"):
        issues.add("SOURCE_IMPORT_WARNINGS")
    # Verify against *all known* physical copper, not just the caller's
    # shortlisted nets, so a target list cannot omit a cut supply return.
    if stepped_path is not None:
        known_nets={str(t["net"]) for family in ("tracks","pads","vias","filled_zones")
                    for t in board.get(family,[]) if t.get("net")}
        check_features=_feature_geometries(board,known_nets,issues)
        physically_cut={f["net"] for f in check_features if f["geometry"].intersects(cut_shape)}
        if physically_cut != requested:
            absent=sorted(physically_cut-requested)
            extra=sorted(requested-physically_cut)
            raise ValueError(f"cut path net inventory mismatch: missing={absent[:8]} extra={extra[:8]}")
    features = _feature_geometries(board, requested, issues)
    if not features:
        raise ValueError("no compatible source copper geometry")
    before = _fragments(features, None, kerf_mm)
    before_ds = _connect(before)
    before_components = _islands(before, before_ds)
    before_of_feature = {f["origin_id"]: (f["net"], before_ds.find(i)) for i, f in enumerate(before)}

    after = _fragments(features, cut_x_mm, kerf_mm, cut_shape=cut_shape,stepped_path=stepped_path)
    after_ds = _connect(after)
    after_groups = _islands(after, after_ds)
    # Only check original *connected copper groups*. Never assume a shared net
    # name proves two separately routed islands were physically connected.
    roots = defaultdict(lambda: defaultdict(list))
    for idx, f in enumerate(after):
        original = before_of_feature.get(f["origin_id"])
        if original is None:
            raise ValueError("source fragment does not map to original feature")
        roots[original][after_ds.find(idx)].append(idx)

    sections = []
    bridge_edges = []
    def seam_at(y):
        return _seam_x_at_y(stepped_path, y, cut_x_mm)

    for original_key in sorted(roots):
        groups = roots[original_key]
        net, original_component = original_key
        if len(groups) <= 1:
            continue
        islands = []
        for suffix, indexes in sorted(groups.items()):
            sides = sorted({after[idx]["side"] for idx in indexes})
            pads = _pad_candidates(after, indexes, cut_x_mm, stepped_path=stepped_path)
            if repair_mode in ("adaptive", "adaptive_functional"):
                contacts = recover_contacts(
                    board, after, indexes, cut_shape or box(
                        cut_x_mm - kerf_mm/2, -1e8, cut_x_mm + kerf_mm/2, 1e8
                    ), seam_at
                )
            else:
                contacts = [
                    {**pad, "contact_type": "existing_pad", "physical_access_verified": False}
                    for pad in pads
                ]
            inert = (classify_inert_cut_remnant(after, indexes)
                     if repair_mode == "adaptive_functional" else None)
            islands.append({
                "model_island_id": f"{net}::pre{original_component}::post{suffix}",
                "sides": sides,
                "copper_fragment_count": len(indexes),
                "intact_solder_pad_candidates": pads,
                "source_copper_contact_candidates": contacts,
                "inert_track_remnant_plan": inert,
                "restoration_required": inert is None,
            })
        needed = [item for item in islands if item["restoration_required"]]
        anchored = [item for item in needed if item["source_copper_contact_candidates"]]
        missing = len(needed) - len(anchored)
        sections.append({
            "net": net,
            "precut_track_only_component": original_component,
            "postcut_track_only_island_count": len(islands),
            "required_island_count": len(needed),
            "planned_inert_track_remnants": len(islands) - len(needed),
            "candidate_graph_edges_needed": max(0,len(needed) - 1),
            "unanchored_islands": missing,
            "islands": islands,
        })
        if not missing and anchored:
            # Each newly severed island needs one modeled graph connection
            # to restore its own pre-cut copper component. A repeated source
            # net name alone is never grounds for connecting unrelated islands.
            hub = anchored[0]
            for follower in anchored[1:]:
                a = hub["source_copper_contact_candidates"][0]
                b = follower["source_copper_contact_candidates"][0]
                bridge_edges.append({
                    "net": net,
                    "from_island": hub["model_island_id"],
                    "to_island": follower["model_island_id"],
                    "from_candidate_contact": a,
                    "to_candidate_contact": b,
                    # Historical contract preserved for genuine pad endpoints.
                    "from_candidate_pad": a if a["contact_type"]=="existing_pad" else None,
                    "to_candidate_pad": b if b["contact_type"]=="existing_pad" else None,
                    "status": "PROPOSED_MODEL_ONLY_NOT_A_WIRING_AUTHORIZATION",
                })
    # Replay the proposed bridge edges in the same *partial* connectivity
    # model. This detects wrong island mapping and demonstrates when the model
    # can close a synthetic cut; it does not prove a physical wire can be made.
    closure = DisjointSet(len(after))
    for idx in range(len(after)):
        closure.union(idx, after_ds.find(idx))
    post_anchor_indexes = {}
    for original_key, groups in roots.items():
        for suffix, indexes in groups.items():
            net, root = original_key
            post_anchor_indexes[f"{net}::pre{root}::post{suffix}"] = indexes[0]
    for candidate in bridge_edges:
        if candidate["from_island"] not in post_anchor_indexes or candidate["to_island"] not in post_anchor_indexes:
            raise ValueError("bridge points to unknown copper island")
        closure.union(post_anchor_indexes[candidate["from_island"]],
                      post_anchor_indexes[candidate["to_island"]])
    remaining_splits = sum(
        len({closure.find(indexes[0]) for indexes in groups.values()}) > 1
        for groups in roots.values() if len(groups)>1
    )
    active_islands = {
        i["model_island_id"] for section in sections for i in section["islands"]
        if i["restoration_required"]
    }
    remaining_required_splits = sum(
        len({closure.find(indexes[0]) for suffix,indexes in groups.items()
             if f"{original[0]}::pre{original[1]}::post{suffix}" in active_islands}) > 1
        for original,groups in roots.items() if len(groups)>1
    )
    damaged_pads = [
        {"net":f["net"], "ref":f["pad"]["ref"], "pad":f["pad"]["pad"]}
        for f in features if f["kind"]=="pad" and f["pad"]
        and (cut_shape or box(cut_x_mm-kerf_mm/2,-1e8,cut_x_mm+kerf_mm/2,1e8)).intersects(f["geometry"])
    ]
    baseline_terminal_islands = defaultdict(set)
    for i,f in enumerate(before):
        if f["kind"] == "pad" and f["pad"]:
            baseline_terminal_islands[f["net"]].add(before_ds.find(i))
    preexisting_terminal_disconnections={
        net:len(roots_) for net,roots_ in baseline_terminal_islands.items() if len(roots_)>1
    }
    result = {
        "schema": "hs.keyboard-postcut-copper-islands.v1",
        "source_sha256": board["source_sha256"],
        "cut_x_mm": cut_x_mm,
        "cut_path_sha256": path_digest,
        "cut_path_kind": "stepped_polyline" if stepped_path is not None else "straight",
        "kerf_mm": kerf_mm,
        "model_basis": "KiCad tracks/pads/vias and explicit filled copper zone polygons; unsupported pad shapes remain blocked",
        "repair_mode": repair_mode,
        "trace_exposure_requires_mask_removal_and_strain_relief": repair_mode in ("adaptive","adaptive_functional"),
        "conductive_zones_imported": len(board.get("filled_zones", [])),
        "rule_areas_ignored_for_connectivity": board.get("rule_area_count",0),
        "qualified_for_build": False,
        "target_net_count": len(requested),
        "model_pre_cut_island_count": len(before_components),
        "model_post_cut_island_count": len(after_groups),
        "split_pre_cut_components": len(sections),
        "candidate_graph_edges": len(bridge_edges),
        "unanchored_split_components": sum(x["unanchored_islands"]>0 for x in sections),
        "model_replay_remaining_split_components": remaining_splits,
        "model_replay_remaining_required_components": remaining_required_splits,
        "model_replay_achieved_required_restoration": remaining_required_splits == 0 and bool(sections)
            and not damaged_pads,
        "planned_inert_track_remnants": sum(
            x["planned_inert_track_remnants"] for x in sections
        ),
        "damaged_electrical_pad_count": len(damaged_pads),
        "damaged_electrical_pads": damaged_pads,
        "preexisting_unconnected_terminal_net_count": len(preexisting_terminal_disconnections),
        "preexisting_unconnected_terminal_nets": preexisting_terminal_disconnections,
        "model_replay_achieved_full_restoration": remaining_splits == 0 and bool(sections),
        "issues": sorted(issues),
        "sections": sections,
        "bridge_edges": bridge_edges,
        "release": "BLOCKED_REFERENCE_TOPOLOGY_ONLY",
    }
    # Content-bound checksum lets the outer HS operator ensure the generated
    # report was not silently swapped before it is attached to its handoff.
    payload = json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    result["payload_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--board-json",type=Path,required=True)
    ap.add_argument("--net-inventory-json",type=Path,required=True)
    ap.add_argument("--cut-path-json",type=Path,default=None)
    ap.add_argument("--cut-x-mm",type=float,required=True)
    ap.add_argument("--kerf-mm",type=float,default=1.0)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--bridge-csv",type=Path)
    ap.add_argument("--repair-mode",choices=("pad_only","adaptive","adaptive_functional"),default="pad_only")
    args=ap.parse_args()
    body=json.loads(args.board_json.read_text(encoding="utf-8"))
    names=json.loads(args.net_inventory_json.read_text(encoding="utf-8"))
    path=json.loads(args.cut_path_json.read_text(encoding="utf-8")) if args.cut_path_json else None
    result=simulate_islands(body,args.cut_x_mm,args.kerf_mm,names,cut_path=path,repair_mode=args.repair_mode)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if args.bridge_csv:
        args.bridge_csv.parent.mkdir(parents=True,exist_ok=True)
        with args.bridge_csv.open("w",encoding="utf-8",newline="") as f:
            writer=csv.writer(f,lineterminator="\n")
            writer.writerow(["net","from_pad","to_pad","model_status"])
            for edge in result["bridge_edges"]:
                x,y=edge["from_candidate_contact"],edge["to_candidate_contact"]
                writer.writerow([edge["net"],str(x["ref"])+"/"+str(x["pad"]),
                                 str(y["ref"])+"/"+str(y["pad"]),edge["status"]])
    print("MODELED_SOURCE_ISLANDS",result["model_pre_cut_island_count"])
    print("MODELED_POSTCUT_ISLANDS",result["model_post_cut_island_count"])
    print("SPLIT_PRECUT_GROUPS",result["split_pre_cut_components"])
    print("CANDIDATE_BRIDGE_EDGES",result["candidate_graph_edges"])
    print("UNANCHORED_GROUPS",result["unanchored_split_components"])
    print("REQUIRED_REMAINING",result["model_replay_remaining_required_components"])
    print("ISOLATE_INERT",result["planned_inert_track_remnants"])
    print("DAMAGED_COPPER_PADS",result["damaged_electrical_pad_count"])
    print("PREEXISTING_TERMINAL_NET_GAPS",result["preexisting_unconnected_terminal_net_count"])
    print("ISSUES",",".join(result["issues"]))
    print("VERDICT",result["release"])


if __name__=="__main__":
    main()
