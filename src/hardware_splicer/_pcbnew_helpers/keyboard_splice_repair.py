"""Model-based copper contact recovery for PCB reuse.

Finds *existing* copper pads, via barrels, and bounded trace exposure candidates
on the post-cut island. A trace contact means remove solder mask and add a
mechanically secured micro-wire; it is NEVER an assertion of solderability.
"""
from __future__ import annotations

from shapely.geometry import LineString, Point


def _line_parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry]
    return [piece for sub in getattr(geometry, "geoms", ()) for piece in _line_parts(sub)]


def _distance(contact, cut_shape):
    if cut_shape is None:
        return 100.0
    return Point(contact["x"], contact["y"]).distance(cut_shape)


def recover_contacts(board, fragments, component_indices, cut_shape, seam_at_y,
                     min_trace_mm=2.0, min_trace_width_mm=0.35,
                     cut_margin_mm=1.0):
    """Return source-backed candidate contacts for a single connected island.

    Existing pads are preferred; via annular copper and trace exposure are
    explicit *repair methods*, not real pads, with physical verification blocked.
    """
    options = []
    seen = set()
    for index in component_indices:
        fragment = fragments[index]
        net = fragment["net"]
        kind = fragment["kind"]
        if kind == "pad" and fragment["intact_pad"]:
            p = fragment.get("pad")
            if p:
                key = ("existing_pad", str(p.get("ref")), str(p.get("pad")))
                if key not in seen:
                    seen.add(key)
                    options.append({
                        "contact_type": "existing_pad",
                        "ref": str(p.get("ref", "")),
                        "pad": str(p.get("pad", "")),
                        "x": round(float(p["x"]), 4),
                        "y": round(float(p["y"]), 4),
                        "layer": fragment["layer"],
                        "net": net,
                        "source_geometry_id": fragment["origin_id"],
                        "exposure_length_mm": None,
                        "conductor_width_mm": None,
                        "physical_access_verified": False,
                        "inspection": "Confirm exact populated component and solderability",
                    })
        if kind == "via":
            via_index = int(fragment["origin_id"].split(":")[1])
            via = board["vias"][via_index]
            diameter = float(via["diameter_mm"])
            pt = Point(float(via["x"]), float(via["y"]))
            # Sawn or edge-near vias cannot be trusted as intact barrels.
            if diameter < 0.8 or (cut_shape is not None and
                pt.distance(cut_shape) <= diameter / 2 + cut_margin_mm):
                continue
            key = ("via_annulus", via_index)
            if key not in seen:
                seen.add(key)
                options.append({
                    "contact_type": "via_annulus",
                    "ref": f"VIA{via_index}",
                    "pad": "ANNULUS",
                    "x": round(pt.x, 4),
                    "y": round(pt.y, 4),
                    "layer": fragment["layer"],
                    "net": net,
                    "source_geometry_id": fragment["origin_id"],
                    "exposure_length_mm": None,
                    "conductor_width_mm": round(diameter, 4),
                    "physical_access_verified": False,
                    "inspection": "Verify via plating, tenting, annulus, access and wire strain relief",
                })
        if kind == "track":
            track_index = int(fragment["origin_id"].split(":")[1])
            track = board["tracks"][track_index]
            width = float(track.get("width_mm", 0))
            if width < min_trace_width_mm:
                continue
            centerline = LineString([
                (float(track["x1"]), float(track["y1"])),
                (float(track["x2"]), float(track["y2"])),
            ])
            # The only allowable copper comes from this exact surviving track
            # fragment and not an invented connection across the saw corridor.
            eligible = centerline.intersection(fragment["geometry"])
            if cut_shape is not None:
                eligible = eligible.difference(cut_shape.buffer(cut_margin_mm))
            segments = sorted(_line_parts(eligible), key=lambda seg: seg.length, reverse=True)
            if not segments or segments[0].length < min_trace_mm:
                continue
            longest = segments[0]
            pt = longest.interpolate(0.5, normalized=True)
            key = ("trace_exposure", track_index, round(pt.x, 3), round(pt.y, 3))
            if key not in seen:
                seen.add(key)
                options.append({
                    "contact_type": "trace_exposure",
                    "ref": f"TRACK{track_index}",
                    "pad": "MASK_OPEN_WINDOW",
                    "x": round(pt.x, 4),
                    "y": round(pt.y, 4),
                    "layer": fragment["layer"],
                    "net": net,
                    "source_geometry_id": fragment["origin_id"],
                    "exposure_length_mm": round(longest.length, 4),
                    "conductor_width_mm": round(width, 4),
                    "physical_access_verified": False,
                    "inspection": "Inspect mask removal, neighboring nets, wire-gauge support and adhesive strain relief",
                })

    category = {"existing_pad": 0, "via_annulus": 1, "trace_exposure": 2}
    options.sort(key=lambda p: (
        category[p["contact_type"]],
        abs(float(p["x"]) - seam_at_y(float(p["y"]))),
        -float(p["exposure_length_mm"] or 0),
        p["ref"], p["pad"],
    ))
    return options[:6]


def classify_inert_cut_remnant(fragments, component_indices, *, max_area_mm2=7.0):
    """Only prune tiny isolated *track-only* scraps, never components/zones/vias.

    These are electrical dead ends once the material removal has happened.
    This is a counterfactual plan to isolate/discard copper, not a claim that
    the real board or its key matrix has passed acceptance.
    """
    if not component_indices:
        return None
    kinds = {fragments[i]["kind"] for i in component_indices}
    if kinds != {"track"}:
        return None
    total_area = sum(float(fragments[i]["geometry"].area) for i in component_indices)
    if total_area <= 0 or total_area > max_area_mm2:
        return None
    return {
        "decision": "PLAN_ISOLATE_TRACK_ONLY_REMNANT",
        "total_modeled_copper_area_mm2": round(total_area, 4),
        "track_fragment_count": len(component_indices),
        "retained_electrical_terminal_count": 0,
        "physical_discard_verified": False,
        "inspection": "Confirm fragment is not a key/MCU/connector terminal; remove sharp free copper and insulate",
    }
