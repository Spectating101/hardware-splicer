"""Measure emitted contours and evaluate worst-case fabrication and loading envelopes."""

import json
import math
import struct
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET


HERE = Path(__file__).resolve().parent
NS = {"s": "http://www.w3.org/2000/svg"}


def measure(name):
    svg = ET.parse(HERE / (name + ".svg")).getroot()
    outline = svg.find("s:rect[@id='outline']", NS)
    length, width = (float(outline.attrib[k]) for k in ("width", "height"))
    assert (svg.get("width"), svg.get("height")) == (f"{length:g}mm", f"{width:g}mm")
    assert list(map(float, svg.get("viewBox").split())) == [0, 0, length, width]
    assert float(outline.get("x")) == float(outline.get("y")) == 0
    holes = sorted(tuple(float(c.get(k)) for k in ("cx", "cy", "r"))
                   for c in svg.findall("s:circle", NS))
    window = svg.find("s:rect[@id='aperture']", NS)
    aperture = None
    if window is not None:
        aperture = float(window.get("width"))
        assert aperture == float(window.get("height"))
        assert math.isclose(2 * float(window.get("x")) + aperture, length)
        assert math.isclose(2 * float(window.get("y")) + aperture, width)
    return length, width, holes, aperture


def assembled_dimensions(d, profile):
    length, width, holes, base_opening = measure("base")
    m_length, m_width, m_holes, mask_opening = measure("mask")
    assert (length, width, holes) == (m_length, m_width, m_holes)
    assert (length, width) == (d["sheet_length_mm"], d["sheet_width_mm"])
    assert base_opening == d["base_window_mm"] and mask_opening == d["mask_window_mm"]
    assert len(holes) == 4 and all(2*h[2] == d["locator_diameter_mm"] for h in holes)
    gaps = []
    for part in ("support", "guide-" + profile):
        strip_length, strip_width, strip_holes, window = measure(part)
        assert strip_length == length and window is None and len(strip_holes) == 2
        opposite = [(x, width-y, r) for x, y, r in strip_holes]
        assert sorted(strip_holes+opposite) == holes
        gaps.append(width-2*strip_width)
    assert math.isclose(gaps[0], d["support_gap_mm"])
    assert math.isclose(gaps[1], d["guide_profiles"][profile]["gap_mm"])
    return dict(length=length, base=base_opening, mask=mask_opening, support=gaps[0], guide=gaps[1])


def assess(geometry, d, min_width, max_width):
    angle = math.radians(d["loading_skew_deg"])
    ray = math.tan(math.radians(d["optical_ray_half_angle_deg"]))
    minimum_gap = geometry["guide"] - d["guide_gap_error_mm"]
    maximum_gap = geometry["guide"] + d["guide_gap_error_mm"]
    # Width swept by a long strip through the full length of parallel side guides.
    swept = max_width / math.cos(angle) + geometry["length"] * math.tan(angle)
    lateral_float = max(0.0, (maximum_gap-min_width)/2)
    film_extent = d["frame_side_mm"] / 2 * (math.cos(angle) + math.sin(angle))
    registration = d["layer_to_guide_center_error_mm"]
    frame_y = film_extent + lateral_float + d["image_to_strip_center_error_mm"] + registration
    frame_x = film_extent + d["longitudinal_centering_error_mm"] + registration
    high_slot = d["guide_thickness_mm"] + d["guide_height_error_mm"]
    upper_height = d["mask_thickness_mm"] + high_slot
    ledge_height = d["support_thickness_mm"] + high_slot
    base_height = ledge_height + d["base_thickness_mm"]
    # Assume a displacement of the adverse sign independently at each layer.
    mask_radius = (geometry["mask"] - d["window_size_error_mm"]) / 2
    base_radius = (geometry["base"] - d["window_size_error_mm"]) / 2
    support_radius = (geometry["support"] - d["support_gap_error_mm"]) / 2
    margins = {
        "loading_clearance_mm": minimum_gap - swept,
        "reload_span_at_center_mm": 2*lateral_float,
        "vertical_clearance_mm": d["guide_thickness_mm"] - d["guide_height_error_mm"] - d["film_total_thickness_max_mm"],
        "camera_mask_margin_mm": mask_radius-max(frame_x,frame_y)-upper_height*ray,
        "illuminator_base_margin_mm": base_radius-max(frame_x,frame_y)-base_height*ray,
        "edge_ledge_optical_margin_mm": support_radius-frame_y-ledge_height*ray,
        "minimum_edge_support_mm": (min_width-geometry["support"]-d["support_gap_error_mm"])/2
                                   - lateral_float - registration - geometry["length"]/2*math.tan(angle),
    }
    checks = {
        "slides_without_geometric_binding": margins["loading_clearance_mm"] >= d["minimum_loading_clearance_mm"],
        "lateral_reload_span": margins["reload_span_at_center_mm"] <= d["maximum_lateral_reload_span_mm"],
        "thickness_clearance": margins["vertical_clearance_mm"] >= d["minimum_vertical_clearance_mm"],
        "full_frame_visible": min(margins[k] for k in ("camera_mask_margin_mm", "illuminator_base_margin_mm", "edge_ledge_optical_margin_mm")) >= 0,
        "supported_on_both_edges": margins["minimum_edge_support_mm"] >= d["minimum_edge_support_mm"],
    }
    return {"margins": {k: round(v, 4) for k, v in margins.items()}, "checks": checks}


def check_stl(part, height):
    length,width,holes,opening = measure(part)
    mesh = (HERE / (part+".stl")).read_bytes()
    count = struct.unpack_from("<I", mesh, 80)[0]
    assert len(mesh) == 84+50*count
    directed = Counter()
    vertices = set()
    volume = 0.0
    for record in struct.iter_unpack("<12fH", mesh[84:]):
        a,b,c = record[3:6],record[6:9],record[9:12]
        assert len({a,b,c}) == 3
        vertices.update((a,b,c))
        directed.update(((a,b),(b,c),(c,a)))
        cross = (b[1]*c[2]-b[2]*c[1], b[2]*c[0]-b[0]*c[2], b[0]*c[1]-b[1]*c[0])
        volume += sum(v*n for v,n in zip(a,cross))/6
    assert all(count == directed[(b,a)] == 1 for (a,b),count in directed.items())
    actual = [[min(v[i] for v in vertices),max(v[i] for v in vertices)] for i in range(3)]
    assert all(abs(low)<1e-5 and abs(high-target)<1e-5 for (low,high),target in zip(actual,(length,width,height)))
    # The STL uses regular 48-sided locator holes; the SVG uses exact circles.
    hole_area = sum(24*r*r*math.sin(math.tau/48) for x,y,r in holes)
    target = (length*width - (opening or 0)**2 - hole_area)*height
    assert math.isclose(volume,target,rel_tol=1e-5)
    return {"triangles":count, "closed_oriented_mesh":True, "volume_mm3":round(volume,3)}


def main():
    d = json.loads((HERE / "design.json").read_text())
    results = {"profiles": {}, "negative_controls": {}, "meshes": {}}
    for part in ("base","mask","support","guide-narrow","guide-wide"):
        thickness = d[part.split("-")[0]+"_thickness_mm"]
        results["meshes"][part] = check_stl(part, thickness)
    for name, bounds in d["guide_profiles"].items():
        g = assembled_dimensions(d, name)
        result = assess(g, d, bounds["film_width_min_mm"], bounds["film_width_max_mm"])
        assert all(result["checks"].values()), (name, result)
        results["profiles"][name] = result
    narrow, wide = (assembled_dimensions(d, name) for name in ("narrow", "wide"))
    # Rejected envelopes must fail for the declared reason or the digital check fails.
    controls = [
        ("single_wide_guide_on_narrow_strip",wide,d,60.70,61.70,"lateral_reload_span"),
        ("wide_film_in_narrow_guide",narrow,d,61.70,61.70,"slides_without_geometric_binding"),
        ("58_mm_exposure",narrow,{**d,"frame_side_mm":58},60.70,61.20,"full_frame_visible"),
        ("skewed_insertion",wide,{**d,"loading_skew_deg":0.35},61.20,61.70,"slides_without_geometric_binding"),
        ("thick_media",narrow,{**d,"film_total_thickness_max_mm":0.27},60.70,61.20,"thickness_clearance"),
        ("20_degree_optical_ray",narrow,{**d,"optical_ray_half_angle_deg":20},60.70,61.20,"full_frame_visible"),
    ]
    for name, g, conf, lo, hi, intended in controls:
        result = assess(g, conf, lo, hi)
        assert not result["checks"][intended], (name, intended, result)
        results["negative_controls"][name] = result
    (HERE / "verification.json").write_text(json.dumps(results, indent=2)+"\n")
    print("Five closed solids verified. Two guide profiles passed five checks each; six adverse controls detected.")


if __name__ == "__main__":
    main()
