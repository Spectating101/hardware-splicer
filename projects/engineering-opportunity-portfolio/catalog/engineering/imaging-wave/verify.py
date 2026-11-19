"""Validate exported geometry and compare digital baseline and revised coupons."""
import csv
import itertools
import json
import math
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build import PARAMS, ROOT, export

SVG = "{http://www.w3.org/2000/svg}"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def attributes(node, *keys):
    return tuple(float(node.attrib[key]) for key in keys)


def points(node):
    return [tuple(map(float, point.split(","))) for point in node.attrib["points"].split()]


def extent(node):
    kind = node.tag.removeprefix(SVG)
    if kind == "rect":
        x, y, w, h = attributes(node, "x", "y", "width", "height")
        require(w > 0 and h > 0, f"Invalid rectangle {node.attrib['id']}")
        return x, y, x+w, y+h
    if kind == "circle":
        x, y, r = attributes(node, "cx", "cy", "r")
        require(r > 0, f"Invalid circle {node.attrib['id']}")
        return x-r, y-r, x+r, y+r
    if kind == "line":
        x1, y1, x2, y2 = attributes(node, "x1", "y1", "x2", "y2")
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    if kind == "polygon":
        x, y = zip(*points(node))
        return min(x), min(y), max(x), max(y)
    require(kind == "text", f"Unexpected shape {kind}")
    x, y = attributes(node, "x", "y")
    return x, y, x, y


def svg(path):
    root = ET.parse(path).getroot()
    require(root.tag == SVG+"svg", f"{path} is not SVG")
    require(all(root.attrib[key].endswith("mm") for key in ("width", "height")),
            f"{path} requires millimeter units")
    w, h = (float(root.attrib[key][:-2]) for key in ("width", "height"))
    view = tuple(map(float, root.attrib["viewBox"].split()))
    require(view == (0, 0, w, h), f"{path} has inconsistent sheet scaling")
    require(not any("transform" in n.attrib for n in root.iter()), f"{path} has a hidden scale or offset")
    children = [n for n in root if n.tag != SVG+"title"]
    elements = {n.attrib["id"]: n for n in children}
    require(len(elements) == len(children), f"{path} has duplicate shape identifiers")
    require(attributes(elements["scale"], "width", "height") == (20, 10), f"{path} scale coupon failed")
    for key, node in elements.items():
        x1, y1, x2, y2 = extent(node)
        require(x1 >= 0 and y1 >= 0 and x2 <= w and y2 <= h, f"{path} {key} lies outside sheet")
        require(node.attrib["data-operation"] in {"cut", "engrave", "reference"},
                f"{path} {key} has no recognized operation")
    return elements


def size(node):
    if node.tag == SVG+"rect":
        return attributes(node, "width", "height")
    x1, y1, x2, y2 = extent(node)
    return x2-x1, y2-y1


def measure(value, relation, limit, unit):
    predicates = {"min": value >= limit-1e-7, "max": value <= limit+1e-7}
    return {"value": round(value, 5), "target": relation, "limit": limit, "unit": unit,
            "pass": predicates[relation]}


def film(nodes, p, path):
    gap = extent(nodes["guide-lower"])[1] - extent(nodes["guide-upper"])[3]
    window_x, window_y = size(nodes["base-window"])
    require(size(nodes["base-window"]) == size(nodes["lid-window"]), "Film mask sizes differ")
    for name in ("base", "lid"):
        mask = extent(nodes[f"{name}-window"])
        blank = extent(nodes[f"{name}-blank"])
        require(all(math.isclose(mask[i]+mask[i+2], blank[i]+blank[i+2], abs_tol=1e-6)
                    for i in (0, 1)), "Film mask aperture off center")
    min_slip = gap - p["guide_gap_error_mm"] - max(p["stock_mm"])
    reload = gap + p["guide_gap_error_mm"] - min(p["stock_mm"])
    alignment = reload/2 + p["mask_align_mm"]
    return {
        "Minimum insertion clearance": measure(min_slip, "min", 0.20, "mm"),
        "Worst lateral reload span": measure(reload, "max", 1.0, "mm"),
        "Vertical frame margin": measure((window_y-p["coupon_frames_mm"][1])/2-alignment, "min", 0.25, "mm"),
        "Horizontal frame margin": measure((window_x-p["coupon_frames_mm"][0])/2-p["feed_reg_mm"]-p["mask_align_mm"], "min", 0.25, "mm"),
        "Perforation exclusion margin": measure(p["min_perforation_distance_mm"]-window_y/2-alignment, "min", 0.25, "mm"),
    }


def indexed(nodes, p, path):
    with path.with_name(path.stem+"-capture.csv").open(newline="", encoding="utf-8") as f:
        events = [tuple(int(r[k]) for k in ("index", "position_steps", "hold_before_capture_ms", "capture"))
                  for r in csv.DictReader(f)]
    first, last = events[0], events[-1]
    capture_count = p["captures"]
    require(len(events) == capture_count+1 and first[1] == 0 and last[3] == 0, "Index endpoint invalid")
    require(all(a[0]+1 == b[0] and a[1] < b[1] and a[3] == 1 for a,b in zip(events, events[1:])),
            "Index sequence is broken")
    cx, cy = attributes(nodes["dial"], "cx", "cy")
    step_to_deg = 360 / p["steps_per_rev"]
    deviations = []
    for idx, step, _, _ in events[:-1]:
        x, y = attributes(nodes[f"tick-{idx}"], "x2", "y2")
        drawn = math.degrees(math.atan2(x-cx, cy-y)) % 360
        emitted = step * step_to_deg
        require(abs((drawn-emitted+180)%360-180) <= 0.00001, "Index schedule and engraved ticks disagree")
        deviations.append(abs(emitted-idx*360/capture_count))
    dwell = min(e[2] for e in events[:-1])
    return {
        "Worst nominal index error": measure(max(deviations), "max", 0.1, "deg"),
        "Home closure error": measure(abs(last[1]*step_to_deg-360), "max", 0.1, "deg"),
        "Settling time budget surplus": measure(dwell-p["settle_ms"]-p["extra_ms"], "min", 0, "ms"),
    }


def deck(nodes, p, path):
    center = attributes(nodes["deck"], "cx", "cy")
    feet = [attributes(nodes[f"host-foot-{i}"], "cx", "cy") for i in range(4)]
    distances = []
    for a,b in zip(feet, feet[1:]+feet[:1]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        distances.append(abs((center[0]-a[0])*dy-(center[1]-a[1])*dx) / math.hypot(dx, dy))
    load_r, = attributes(nodes["safe-cog-zone"], "r")
    total_mass = p["base_mass"] + p["deck_mass"] + p["load_mass"]
    object_shift = load_r * p["load_mass"] / total_mass
    push_shift = 1000*p["push_n"]*p["load_height"] / (total_mass*9.80665)
    def key_spacing(part):
        a = attributes(nodes[f"{part}-pilot"], "cx", "cy")
        b = attributes(nodes[f"{part}-key"], "cx", "cy")
        return math.dist(a,b)
    require(abs(key_spacing("deck")-key_spacing("hub")) <= 0.01, "Hub and deck key index differ")
    socket_d, _ = size(nodes["hub-key"])
    return {
        "Worst projected stability margin": measure(min(distances)-object_shift-push_shift, "min", 10, "mm"),
        "Offset drive pin spacing": measure(key_spacing("hub"), "min", 15, "mm"),
        "Offset drive pin diametral relief": measure(socket_d-p["socket_pin_d_mm"], "min", 0.35, "mm"),
    }


def photo_box(nodes, p, path):
    w, d = size(nodes["floor"])
    leaves = []
    open_depth = []
    for i in range(2):
        inner = nodes[f"side-{i}-inner"]
        outer = nodes.get(f"side-{i}-outer")
        inner_w, _ = size(inner)
        outer_w = size(outer)[0] if outer is not None else 0
        gap = extent(outer)[0]-extent(inner)[2] if outer is not None else 0
        leaves.append(max(inner_w, outer_w))
        open_depth.append(inner_w+outer_w+gap)
    hinge_offset = min(extent(nodes[f"hinge-offset-{i}"])[0]-extent(nodes[f"side-{i}-inner"])[0]
                       for i in range(2))
    fold_layers = 2 if any(f"side-{i}-outer" in nodes for i in range(2)) else 1
    return {
        "Clearance between stowed side packs": measure(w-sum(leaves)-2*p["stack_displacement_mm"], "min", 4, "mm"),
        "Useable open side depth": measure(min(open_depth), "min", d-8, "mm"),
        "Hinge offset surplus over packed stock": measure(hinge_offset-fold_layers*p["stock_thickness"], "min", .8, "mm"),
    }


def portal(nodes, p, path):
    span = extent(nodes["post-center-1"])[0] - extent(nodes["post-center-0"])[0]
    width, depth = size(nodes["section-gauge"])
    modulus = p["lower_modulus_n_mm2"]
    linear_load = p["load_with_self_weight_n_mm"]
    inertia = width*depth**3/12
    sag = 5*linear_load*span**4/(384*modulus*inertia)
    peak_stress = linear_load*span**2*depth/(16*inertia)
    return {
        "Modeled maximum sag": measure(sag, "max", 1.0, "mm"),
        "Modeled extreme fiber stress": measure(peak_stress, "max", 5.0, "N/mm²"),
        "Support span": measure(span, "min", 600, "mm"),
    }


def hood(nodes, p, path):
    aperture_w, aperture_h = size(nodes["frame-opening"])
    screen_w, screen_h = size(nodes["screen-reference"])
    top_w, depth = size(nodes["top-panel"])
    require(abs(top_w-aperture_w) < 0.01, "Hood top and front frame widths differ")
    sides = [size(nodes[f"side-panel-{i}"]) for i in range(2)]
    require(all(w == depth and h == aperture_h for w, h in sides), "Hood panels do not close around frame")
    x_shift = depth*math.tan(math.radians(p["horizontal_view_deg"]))
    y_shift = depth*math.tan(math.radians(p["vertical_view_deg"]))
    reg = p["edge_register_mm"]
    shadow = depth*math.tan(math.radians(p["top_light_deg"]))-(aperture_h+screen_h)/2-reg
    return {
        "Full-image horizontal sight margin": measure((aperture_w-screen_w)/2-x_shift-reg, "min", 0.4, "mm"),
        "Full-image vertical sight margin": measure((aperture_h-screen_h)/2-y_shift-reg, "min", 0.4, "mm"),
        "Overhead shadow beyond far screen edge": measure(shadow, "min", 2, "mm"),
    }


def saddle(nodes, p, path):
    rod_a = attributes(nodes["rod-0"], "cx", "cy")
    rod_b = attributes(nodes["rod-1"], "cx", "cy")
    _, optical_y = attributes(nodes["optical-axis"], "cx", "cy")
    require(abs(math.dist(rod_a, rod_b)-60) <= 0.01, "ARRI rod spacing has changed")
    require(abs(rod_a[1]-optical_y-85) <= 0.01, "ARRI axis datum has changed")
    x0, y0, x1, y1 = extent(nodes["adjustment-slot"])
    fastener_clearance = (x1-x0)/2
    min_height = rod_a[1] - (y1-fastener_clearance)
    max_height = rod_a[1] - (y0+fastener_clearance)
    left, apex, right, *_ = points(nodes["saddle-blank"])
    half_angle = math.atan2((right[0]-left[0])/2, apex[1]-(right[1]+left[1])/2)
    tall = rod_a[1]-optical_y
    low = tall-p["axis_error_mm"]-(max(p["lens_diameters_mm"])/2+p["pad_mm"])/math.sin(half_angle)
    high = tall+p["axis_error_mm"]-(min(p["lens_diameters_mm"])/2+p["pad_mm"])/math.sin(half_angle)
    return {
        "Large-lens lower adjustment reserve": measure(low-min_height, "min", 1.0, "mm"),
        "Small-lens upper adjustment reserve": measure(max_height-high, "min", 1.0, "mm"),
        "Nominal rod hole diametral relief": measure(size(nodes["rod-0"])[0]-15, "min", 0.5, "mm"),
    }


def matte_box(nodes, p, path):
    start = extent(nodes["pupil-datum"])[0]
    checks = {}
    for n, key in enumerate(("rear", "filter", "front")):
        distance = extent(nodes[f"plane-{n}"])[0] - start
        aperture = size(nodes[f"{key}-aperture"])
        half_field = [s/(2*p["focal_mm"]) for s in p["sensor_mm"]]
        margins = [a/2-distance*slope-p["pupil_r_mm"]-p["registration_error_mm"]
                   for a,slope in zip(aperture, half_field)]
        checks[f"{key.title()} plane smallest ray clearance"] = measure(min(margins), "min", 1.5, "mm")
    filter_lip = min((f-a)/2 for f,a in zip(size(nodes["filter-envelope"]), size(nodes["filter-aperture"])))
    checks["Filter support land"] = measure(filter_lip, "min", 4.0, "mm")
    return checks


def area(poly):
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly, poly[1:]+poly[:1])))/2


def grid(nodes, p, path):
    hole_coords = [points(node) for name,node in nodes.items() if name.startswith("cell-") and name != "cell-blank"]
    reference = extent(nodes["head-reference"])
    depth = size(nodes["depth-gauge"])[1]
    longest = max(math.dist(a,b) for poly in hole_coords for a,b in itertools.combinations(poly, 2))
    area_total = sum(area(poly) for poly in hole_coords)
    w,h = size(nodes["head-reference"])
    edge = min(min(x-reference[0], y-reference[1], reference[2]-x, reference[3]-y)
               for poly in hole_coords for x,y in poly)
    closest = float("inf")
    for poly_a,poly_b in itertools.combinations(hole_coords,2):
        for a,b in zip(poly_a,poly_a[1:]+poly_a[:1]):
            dx,dy = b[0]-a[0], b[1]-a[1]
            norm = math.hypot(dx,dy)
            distances = [(dx*(y-a[1])-dy*(x-a[0]))/norm for x,y in poly_b]
            # These point-up polygons are clockwise in numerical coordinates.
            separation = min(distances)
            if separation > 0:
                closest = min(separation, closest)
    # Adjacent flat-to-flat web can be obtained from the horizontal centers in one row.
    row_cells = [extent(nodes[f"cell-0-{i}"]) for i in range(p["grid"][0])]
    web = min(b[0]-a[2] for a,b in zip(row_cells,row_cells[1:]))
    return {
        "Geometric hard cutoff half-angle": measure(math.degrees(math.atan2(longest,depth)), "max", 28, "deg"),
        "On-axis open area over clear head": measure(100*area_total/(w*h), "min", 62, "%"),
        "Outer cell edge margin": measure(edge, "min", 1.0, "mm"),
        "Minimum web between neighboring cells": measure(min(closest, web), "min", 0.85, "mm"),
    }


def slate(nodes, p, path):
    font_sizes = []
    write_heights = []
    for i,wanted in enumerate(p["reading_samples"]):
        label = nodes[f"label-{i}"]
        require(label.text == wanted, f"Missing bilingual field {i}")
        font_sizes.append(attributes(label,"font-size")[0])
        write_heights.append(size(nodes[f"write-{i}"])[1])
    gap = size(nodes["jaw-gap-gauge"])[0]
    x1,y1,x2,y2 = extent(nodes["fixed-jaw"])
    cx,cy,r = attributes(nodes["fixed-pivot"], "cx", "cy", "r")
    ligament = min(cx-r-x1, x2-cx-r, cy-r-y1, y2-cy-r)
    strike_travel = (x2-cx)*math.sin(math.radians(p["stroke_limit_deg"]))
    return {
        "Smallest bilingual label size": measure(min(font_sizes), "min", 3.5, "mm"),
        "Smallest writing line height": measure(min(write_heights), "min", 15, "mm"),
        "Nominal hinge side clearance": measure(gap, "min", 0.8, "mm"),
        "Fixed jaw hole ligament": measure(ligament, "min", 4.0, "mm"),
        "Nominal tip opening at travel limit": measure(strike_travel, "min", 90, "mm"),
    }


def prompter(nodes, p, path):
    width,length = size(nodes["glass-blank"])
    screen_w,screen_h = size(nodes["active-source"])
    pocket_w,pocket_h = size(nodes["phone-pocket"])
    phone_w,phone_h = p["phone_mm"]
    cx, cy = attributes(nodes["optical-datum"], "x1", "y1")
    camera_back = cx-extent(nodes["pupil-plane"])[0]
    drop = extent(nodes["phone-trace"])[1]-cy
    gx1, gy1, gx2, gy2 = attributes(nodes["glass-trace"], "x1", "y1", "x2", "y2")
    require(abs(gx1-gy2-gx2+gy1) < 1e-5 and abs(gx1+gy1-cx-cy) < 1e-5,
            "Glass section is not centered at 45 degrees on the optical axis")

    # Reflect the phone into the virtual plane and intersect rays from its corners to the eye box.
    taper = []
    for img_y, eye_y in itertools.product((-screen_h/2,screen_h/2), p["talent_height_range_mm"]):
        rise = eye_y-img_y
        run = p["talent_distance_mm"]+drop
        t = (img_y+drop)/(run-rise)
        taper.extend((math.sqrt(2)*(-drop+t*run),
                      max(abs((1-t)*edge+t*eye_side)
                          for edge,eye_side in itertools.product((-screen_w/2,screen_w/2), p["talent_side_range_mm"]))))
    cue_v = max(abs(v) for v in taper[::2])
    cue_w = max(taper[1::2])

    # Intersect the extreme camera rays with the same physical plane.
    camera_v, camera_w = [], []
    slopes = [math.tan(math.radians(p[k])) for k in ("camera_vertical_deg","camera_horizontal_deg")]
    for y0, sy in itertools.product((-p["camera_pupil_mm"],p["camera_pupil_mm"]), (-slopes[0],slopes[0])):
        run = (camera_back+y0)/(1-sy)
        camera_v.append(abs(math.sqrt(2)*(run-camera_back)))
        camera_w.append(p["camera_pupil_mm"]+run*slopes[1])
    return {
        "Cue ray vertical glass edge clearance": measure(length/2-cue_v, "min", 2, "mm"),
        "Cue ray lateral glass edge clearance": measure(width/2-cue_w, "min", 2, "mm"),
        "Camera ray vertical glass edge clearance": measure(length/2-max(camera_v), "min", 2, "mm"),
        "Camera ray lateral glass edge clearance": measure(width/2-max(camera_w), "min", 2, "mm"),
        "Minimum total phone-pocket relief": measure(min(pocket_w-phone_w,pocket_h-phone_h), "min", 2, "mm"),
    }


TRIALS = {"P008": film, "P017": indexed, "P018": deck, "P019": photo_box, "P020": portal,
          "P195": hood, "P196": saddle, "P199": matte_box, "P200": grid, "P203": slate,
          "P205": prompter}


def evaluate(folder):
    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    results = {}
    for product, check in TRIALS.items():
        results[product] = {}
        common = {k:v for k,v in p[product].items() if k not in ("baseline", "revised")}
        for revision in ("baseline", "revised"):
            path = folder/product/f"{revision}.svg"
            results[product][revision] = check(svg(path), common, path)
    return results


def main():
    artifacts = ROOT/"artifacts"
    results = evaluate(artifacts)
    if "--write-results" in sys.argv:
        (ROOT/"results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    for product, revisions in results.items():
        failed_baseline = [key for key,v in revisions["baseline"].items() if not v["pass"]]
        failed_revised = [key for key,v in revisions["revised"].items() if not v["pass"]]
        require(failed_baseline, f"{product} failed to challenge its baseline")
        require(not failed_revised, f"{product} still has unmet targets: {', '.join(failed_revised)}")
        print(f"{product} · {len(failed_baseline)} baseline failures · {len(revisions['revised'])} revised passes")
    require(results == json.loads((ROOT/"results.json").read_text(encoding="utf-8")), "Published results differ from replay")
    with tempfile.TemporaryDirectory() as directory:
        regenerated = Path(directory)
        export(regenerated)
        files = list(artifacts.rglob("*.*"))
        require(len(files) == len(list(regenerated.rglob("*.*"))), "Fresh export file count differs")
        for path in files:
            require((regenerated/path.relative_to(artifacts)).read_bytes() == path.read_bytes(),
                    f"Fresh export differs for {path}")
    print(f"{len(results)} trials · {len(files)} fresh and byte-compared exports")


if __name__ == "__main__":
    main()
