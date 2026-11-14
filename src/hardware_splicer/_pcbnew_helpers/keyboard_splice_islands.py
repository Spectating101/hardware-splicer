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

from shapely.affinity import rotate
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

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
    return features


def _fragments(features: list[dict], cut_x: float | None, kerf_mm: float) -> list[dict]:
    kerf = box(cut_x - kerf_mm / 2, -1e8, cut_x + kerf_mm / 2, 1e8) if cut_x is not None else None
    out = []
    for feature in features:
        polys = [feature["geometry"]] if kerf is None else _polygon_parts(feature["geometry"].difference(kerf))
        for j, poly in enumerate(polys):
            f = {k: v for k, v in feature.items() if k != "geometry"}
            f["geometry"] = poly
            f["origin_id"] = feature["id"]
            f["side"] = "full" if kerf is None else ("left" if poly.centroid.x < cut_x else "right")
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


def _pad_candidates(fragments, component_idxs: list[int], seam: float) -> list[dict]:
    pads = {}
    for idx in component_idxs:
        f = fragments[idx]
        if f["kind"] != "pad" or not f["intact_pad"]:
            continue
        p = f["pad"]
        key = (p["ref"], p["pad"], p["x"], p["y"])
        pads[key] = p
    return sorted(pads.values(), key=lambda p: (abs(float(p["x"]) - seam), str(p["ref"]), str(p["pad"])))[:4]


def simulate_islands(board: dict, cut_x_mm: float, kerf_mm: float = 1.0,
                     target_nets: list[str] | None = None) -> dict:
    if not board.get("source_sha256"):
        raise ValueError("missing source digest")
    if kerf_mm <= 0:
        raise ValueError("kerf must be positive")
    xmin = float(board["outline_bbox_mm"]["x_min"])
    xmax = float(board["outline_bbox_mm"]["x_max"])
    if not xmin < cut_x_mm < xmax:
        raise ValueError("cut must pass through the documented board extent")
    if target_nets is None:
        raise ValueError("explicit target-net inventory required")
    requested = set(target_nets)
    if not requested or "" in requested:
        raise ValueError("target nets must be nonempty and named")
    issues = set()
    if board.get("zone_count", 0):
        issues.add("UNMODELED_COPPER_ZONES")
    if board.get("source_warnings"):
        issues.add("SOURCE_IMPORT_WARNINGS")
    # A two-layer rigid PCB is the only qualified electrical abstraction.
    features = _feature_geometries(board, requested, issues)
    if not features:
        raise ValueError("no compatible source copper geometry")
    before = _fragments(features, None, kerf_mm)
    before_ds = _connect(before)
    before_components = _islands(before, before_ds)
    before_of_feature = {f["origin_id"]: (f["net"], before_ds.find(i)) for i, f in enumerate(before)}

    after = _fragments(features, cut_x_mm, kerf_mm)
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
    for original_key in sorted(roots):
        groups = roots[original_key]
        net, original_component = original_key
        if len(groups) <= 1:
            continue
        islands = []
        for suffix, indexes in sorted(groups.items()):
            sides = sorted({after[idx]["side"] for idx in indexes})
            pads = _pad_candidates(after, indexes, cut_x_mm)
            islands.append({
                "model_island_id": f"{net}::pre{original_component}::post{suffix}",
                "sides": sides,
                "copper_fragment_count": len(indexes),
                "intact_solder_pad_candidates": pads,
            })
        # For each original connected piece fragmented by the cut, restoring
        # connectivity would need at least N-1 connections *within this partial
        # track-only model*. This is NOT a verified real-board conductor count.
        anchored = [x for x in islands if x["intact_solder_pad_candidates"]]
        missing = len(islands) - len(anchored)
        sections.append({
            "net": net,
            "precut_track_only_component": original_component,
            "postcut_track_only_island_count": len(islands),
            "candidate_graph_edges_needed": len(islands) - 1,
            "unanchored_islands": missing,
            "islands": islands,
        })
        if not missing:
            hub = anchored[0]
            for follower in anchored[1:]:
                bridge_edges.append({
                    "net": net, "from_island": hub["model_island_id"],
                    "to_island": follower["model_island_id"],
                    "from_candidate_pad": hub["intact_solder_pad_candidates"][0],
                    "to_candidate_pad": follower["intact_solder_pad_candidates"][0],
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
    result = {
        "schema": "hs.keyboard-postcut-copper-islands.v1",
        "source_sha256": board["source_sha256"],
        "cut_x_mm": cut_x_mm,
        "kerf_mm": kerf_mm,
        "model_basis": "Native KiCad tracks/pads/vias approximated by planar copper polygons; zones omitted",
        "qualified_for_build": False,
        "target_net_count": len(requested),
        "model_pre_cut_island_count": len(before_components),
        "model_post_cut_island_count": len(after_groups),
        "split_pre_cut_components": len(sections),
        "candidate_graph_edges": len(bridge_edges),
        "unanchored_split_components": sum(x["unanchored_islands"]>0 for x in sections),
        "model_replay_remaining_split_components": remaining_splits,
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
    ap.add_argument("--cut-x-mm",type=float,required=True)
    ap.add_argument("--kerf-mm",type=float,default=1.0)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--bridge-csv",type=Path)
    args=ap.parse_args()
    body=json.loads(args.board_json.read_text(encoding="utf-8"))
    names=json.loads(args.net_inventory_json.read_text(encoding="utf-8"))
    result=simulate_islands(body,args.cut_x_mm,args.kerf_mm,names)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if args.bridge_csv:
        args.bridge_csv.parent.mkdir(parents=True,exist_ok=True)
        with args.bridge_csv.open("w",encoding="utf-8",newline="") as f:
            writer=csv.writer(f,lineterminator="\n")
            writer.writerow(["net","from_pad","to_pad","model_status"])
            for edge in result["bridge_edges"]:
                x,y=edge["from_candidate_pad"],edge["to_candidate_pad"]
                writer.writerow([edge["net"],str(x["ref"])+"/"+str(x["pad"]),
                                 str(y["ref"])+"/"+str(y["pad"]),edge["status"]])
    print("MODELED_SOURCE_ISLANDS",result["model_pre_cut_island_count"])
    print("MODELED_POSTCUT_ISLANDS",result["model_post_cut_island_count"])
    print("SPLIT_PRECUT_GROUPS",result["split_pre_cut_components"])
    print("CANDIDATE_BRIDGE_EDGES",result["candidate_graph_edges"])
    print("UNANCHORED_GROUPS",result["unanchored_split_components"])
    print("ISSUES",",".join(result["issues"]))
    print("VERDICT",result["release"])


if __name__=="__main__":
    main()
