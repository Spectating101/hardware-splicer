#!/usr/bin/env python3
"""Independently audit the delivered A5 inspection-card study ZIP.

Run with the existing HS native CAD environment:
    python -B check_delivery.py STUDY.zip --output audit.json --png audit.png

Reads archived data and CAD only; never imports or executes packaged scripts.
This accepts the specific 210x148 paper / 190x128 drawing / 12mm pen / 3mm lift
brief. It is a digital delivery audit, not a physical-machine acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile

EXPECTED = {
    "drawing_width_mm": 190.0, "drawing_height_mm": 128.0,
    "paper_width_mm": 210.0, "paper_height_mm": 148.0,
    "pen_diameter_mm": 12.0, "pen_lift_mm": 3.0,
}
CENTER, BED, LIFT = 117.5, 235.0, 3.0
OFFSET = (0.0, -19.2)
ART_SCALE = min(EXPECTED["drawing_width_mm"]/100., EXPECTED["drawing_height_mm"]/80.)
CHECKBOX_BOUNDS = {3: (8., 49., 13., 54.), 5: (8., 38., 13., 43.),
                   7: (8., 27., 13., 32.), 9: (8., 16., 13., 21.)}
PAPER = (12.5, 43.5, 222.5, 191.5)
VIEWPORT = (22.5, 53.5, 212.5, 181.5)
XY_TOL, CAD_TOL = 0.0003, 0.00001
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
WORD = re.compile(r"([A-Z])(" + NUMBER + r")\Z")
CASE = "ender3-penplotter"


def close(a, b, tolerance=XY_TOL):
    return math.isfinite(float(a)) and math.isfinite(float(b)) and abs(a-b) <= tolerance


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def same_points(left, right):
    return len(left) == len(right) and all(
        len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
        for a, b in zip(left, right)
    )


def inside(point, rectangle, tolerance=XY_TOL):
    x, y = point[:2]
    return rectangle[0]-tolerance <= x <= rectangle[2]+tolerance and \
        rectangle[1]-tolerance <= y <= rectangle[3]+tolerance


def read_json(raw):
    def invalid(value):
        raise ValueError("Non-finite JSON constant: " + value)
    return json.loads(raw, parse_constant=invalid)


class Audit:
    def __init__(self):
        self.checks = []
        self.metrics = {}

    def check(self, name, passed, detail):
        self.checks.append({"name": name, "passed": bool(passed), "detail": detail})

    def require(self, name, passed, detail):
        self.check(name, passed, detail)
        if not passed:
            raise ValueError(name + ": " + str(detail))


def inspect_archive(path, audit, prefix=""):
    contents = {}
    with ZipFile(path) as archive:
        infos = archive.infolist()
        audit.require(prefix+"bounded_archive", len(infos) <= 512 and
                      sum(x.file_size for x in infos) <= 512*1024*1024,
                      "At most 512 entries and 512 MiB uncompressed.")
        seen = set()
        for entry in infos:
            name = entry.filename
            normalized = name[:-1] if entry.is_dir() else name
            safe = bool(normalized) and "\\" not in normalized and "\x00" not in normalized
            safe &= not PurePosixPath(normalized).is_absolute()
            safe &= ".." not in PurePosixPath(normalized).parts
            safe &= PurePosixPath(normalized).as_posix() == normalized
            safe &= normalized not in seen and not stat.S_ISLNK(entry.external_attr >> 16)
            safe &= not entry.flag_bits & 1
            audit.require(prefix+"safe_member_" + normalized, safe,
                          "Unique relative path; no traversal, symlink or encryption.")
            seen.add(normalized)
            if not entry.is_dir():
                contents[normalized] = archive.read(entry)
    audit.require(prefix+"archive_core_files", all(x in contents for x in (
        "requirements.json", "study-contract.json", "study-verification.json",
        "reports/engineering.json", "reports/simulation.json", "reports/verification.json",
        "simulation/example.svg", "simulation/example.gcode", "simulation/trajectory.csv",
        "sources/prompt-drawing.json", "sources/interface.json")),
        "Registered study, source artwork and actual delivered outputs are present.")
    return contents


def check_contract(data, audit):
    get = lambda name: read_json(data[name])
    req = get("requirements.json")
    contract, receipt = get("study-contract.json"), get("study-verification.json")
    eng, sim, verification = [get("reports/" + n + ".json")
                              for n in ("engineering", "simulation", "verification")]
    summary = receipt.get("summary", {})
    audit.check("exact_requested_dimensions", set(req) == set(EXPECTED) and
                all(finite(req.get(k)) and close(req[k], v, 1e-9) for k, v in EXPECTED.items()),
                {"expected": EXPECTED, "delivered": req})
    audit.check("requirements_agree", all(x.get("requirements") == req
                for x in (contract, eng, sim, summary)),
                "Contract, engineering, simulation and sealed summary agree.")
    audit.check("case_identity", all(x.get("case_id") == CASE
                for x in (contract, receipt, eng, sim, verification, summary)), CASE)
    audit.check("integrity_and_goal_both_pass",
                all(x.get("artifact_integrity") is True for x in (receipt, verification, summary))
                and all(x.get("requirements_met") is True for x in (eng, sim, verification, summary)),
                "Successful integrity and successful requested engineering goals are separate requirements.")
    for name, report in (("engineering", eng), ("simulation", sim)):
        constraints = report.get("constraints", [])
        audit.check(name + "_constraints_pass", bool(constraints) and
                    all(x.get("passed") is True for x in constraints),
                    "Every archived constraint must pass.")
    flags = ("physical_work_requested", "physical_authority_granted",
             "physical_validation", "physical_validation_performed",
             "fabrication_authorized", "power_on_authorized", "firmware_authorized")
    audit.check("digital_only", all(x.get(k, False) is False
                for x in (contract, eng, sim, verification, summary) for k in flags)
                and eng.get("owned_inventory_count") == 0,
                "No physical work, powered test, purchased donor or fabrication is established.")
    hashes = receipt.get("artifact_sha256", {})
    audit.check("sealed_file_inventory", isinstance(hashes, dict) and
                set(hashes) == set(data)-{"study-verification.json"},
                "The seal covers every delivered file except itself, with no omissions or extras.")
    audit.check("sealed_file_hashes", bool(hashes) and all(
                name in data and hashlib.sha256(data[name]).hexdigest() == digest
                for name, digest in hashes.items()), "Recomputed from actual ZIP bytes.")
    sources = contract.get("source_sha256", {})
    audit.check("registered_source_hashes", bool(sources) and all(
                name in data and hashlib.sha256(data[name]).hexdigest() == digest
                for name, digest in sources.items()), "Registered input bytes remain unchanged.")
    interface = get("sources/interface.json")
    audit.check("retained_tool_offset", same_points([interface.get("pen_offset_from_nozzle_xy_mm", [])],
                                                   [OFFSET]), OFFSET)
    audit.check("retained_mount_identity",
                same_points(interface.get("mount_centers_uv_mm", []), [(9.5, 7.55), (23.5, 7.55)])
                and close(interface.get("mount_pitch_mm", -1), 14, CAD_TOL),
                "Manufacturer M3 center pair remains 14 mm apart.")
    return req


def decode_gcode(text):
    position, feed = (CENTER, CENTER, LIFT), 1200.0
    metric = absolute = False
    moves, commands = [], Counter()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        command, words = tokens[0], {}
        if command not in {"G21", "G90", "G0", "G1", "M104", "M140", "M107", "M400"}:
            raise ValueError(f"Unsupported command at line {lineno}: {command}")
        allowed = set("XYZF") if command in {"G0", "G1"} else \
            {"S"} if command in {"M104", "M140"} else set()
        for token in tokens[1:]:
            match = WORD.fullmatch(token)
            if match is None:
                raise ValueError(f"Malformed parameter at line {lineno}: {token}")
            key, value = match[1], float(match[2])
            if key not in allowed or key in words or not math.isfinite(value):
                raise ValueError(f"Unsupported, duplicate or nonfinite word at line {lineno}")
            words[key] = value
        commands[command] += 1
        if command == "G21":
            metric = True
        elif command == "G90":
            absolute = True
        elif command in {"M104", "M140"}:
            if words != {"S": 0.0}:
                raise ValueError(f"Nonzero or missing heater setting at line {lineno}")
        elif command in {"G0", "G1"}:
            if not metric or not absolute or not any(k in words for k in "XYZ"):
                raise ValueError(f"Unqualified motion at line {lineno}")
            target = tuple(words.get(k, position[i]) for i, k in enumerate("XYZ"))
            feed = words.get("F", feed)
            if not 0 < feed <= 1200:
                raise ValueError(f"Invalid feed at line {lineno}")
            drawing = position[2] == target[2] == 0 and math.dist(position[:2], target[:2]) > 1e-8
            moves.append({"line": lineno, "start": position, "end": target,
                          "feed": feed, "duration": math.dist(position, target)/(feed/60),
                          "drawing": drawing})
            position = target
    if not moves or not all(commands[k] for k in ("G21", "G90", "M104", "M140", "M400")):
        raise ValueError("Missing motion, explicit metric/absolute mode, heater-off command or completion.")
    return moves


def source_segments(data, audit):
    drawing = read_json(data["sources/prompt-drawing.json"])
    valid = isinstance(drawing, list) and bool(drawing)
    valid &= all(isinstance(s, list) and len(s) >= 2 and
                 all(isinstance(p, list) and len(p) == 2 and all(finite(v) for v in p)
                     and 0 <= p[0] <= 100 and 0 <= p[1] <= 80 for p in s) for s in drawing)
    audit.require("archived_artwork_format", valid, "Nonempty strokes on the archived 100x80 logical canvas.")
    authored = [[(CENTER+(x-50)*ART_SCALE, CENTER+(y-40)*ART_SCALE) for x, y in stroke] for stroke in drawing]
    svg = ET.fromstring(data["simulation/example.svg"])
    audit.require("svg_logical_canvas", svg.attrib.get("viewBox", "").split() == ["0", "0", "100", "80"],
                  "The vector canvas is explicit, with physical scaling checked separately.")
    paths = []
    for node in svg.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in {"svg", "g", "polyline"} or "transform" in node.attrib:
            raise ValueError("Unsupported SVG element or transform: " + tag)
        if tag == "polyline":
            values = re.split(r"[\s,]+", node.attrib["points"].strip())
            if len(values) < 4 or len(values) % 2 or any(not re.fullmatch(NUMBER, v) for v in values):
                raise ValueError("Invalid SVG polyline coordinates")
            points = [float(v) for v in values]
            paths.append([(CENTER+(points[i]-50)*ART_SCALE, CENTER+(40-points[i+1])*ART_SCALE)
                          for i in range(0, len(points), 2)])
    audit.check("prompt_to_svg_stroke_identity", len(paths) == len(authored) and
                all(same_points(a, b) for a, b in zip(paths, authored)),
                "Every directed point and stroke matches archived prompt artwork after independent scaling.")
    boxes, cursor = [], 0
    for index, stroke in enumerate(drawing):
        if index in CHECKBOX_BOUNDS:
            x0, y0, x1, y1 = CHECKBOX_BOUNDS[index]
            expected_corners = {(x0, y0), (x1, y0), (x1, y1), (x0, y1)}
            audit.check("source_checkbox_"+str(index), len(stroke) == 5 and stroke[0] == stroke[-1]
                        and set(map(tuple, stroke[:-1])) == expected_corners,
                        "Actual author-supplied checkbox is a closed 5x5 logical square.")
            boxes.append((index, cursor, cursor+len(stroke)-1))
        cursor += len(stroke)-1
    audit.check("four_archived_checkboxes", len(boxes) == 4, "Actual authored checkbox stroke indices3,5,7,9.")
    return [(a, b) for path in paths for a, b in zip(path, path[1:])], len(paths), boxes


def check_motion(data, audit):
    moves = decode_gcode(data["simulation/example.gcode"].decode("utf-8"))
    audit.check("strict_gcode_decode", True, "Only explicit absolute metric linear motion and emitted heater-off/control commands.")
    all_controller = [p for move in moves for p in (move["start"], move["end"])]
    all_tip = [(p[0]+OFFSET[0], p[1]+OFFSET[1], p[2]) for p in all_controller]
    audit.check("controller_235mm_bounds", all(inside(p, (0, 0, BED, BED)) for p in all_controller),
                "All start/end positions; linear segments stay within their endpoint bounds.")
    audit.check("pen_tip_235mm_bounds", all(inside(p, (0, 0, BED, BED)) for p in all_tip),
                "Source tool compensation applied independently.")
    audit.check("all_z_within_requested_lift", all(-1e-8 <= p[2] <= LIFT+1e-8 for p in all_controller),
                "All moves stay between paper zero and requested 3 mm lift.")
    travel = [m for m in moves if not m["drawing"] and math.dist(m["start"][:2], m["end"][:2]) > 1e-8]
    audit.check("all_xy_travel_pen_up", all(close(m[k][2], LIFT, 1e-8)
                for m in travel for k in ("start", "end")), "Every non-drawing XY move has 3 mm lift at both endpoints.")
    audit.check("final_pen_lifted", close(moves[-1]["end"][2], LIFT, 1e-8), "The delivered job ends with the pen raised.")
    ink = [((m["start"][0]+OFFSET[0], m["start"][1]+OFFSET[1]),
            (m["end"][0]+OFFSET[0], m["end"][1]+OFFSET[1])) for m in moves if m["drawing"]]
    audit.require("nonempty_ink", bool(ink), "The job draws actual line segments.")
    expected, strokes, boxes = source_segments(data, audit)
    audit.check("svg_to_gcode_directed_segments", len(ink) == len(expected) and
                all(same_points(a, b) for a, b in zip(ink, expected)),
                {"delivered_segments": len(ink), "source_segments": len(expected),
                 "tolerance_mm": XY_TOL, "order_preserved": True})
    dimensions = []
    square = len(boxes) == 4
    for index, first, stop in boxes:
        segments = ink[first:stop]
        if len(segments) != 4:
            square = False
            continue
        points = [p for segment in segments for p in segment]
        width = max(p[0] for p in points)-min(p[0] for p in points)
        height = max(p[1] for p in points)-min(p[1] for p in points)
        square &= close(width, 8.) and close(height, 8.)
        square &= same_points([segments[-1][-1]], [segments[0][0]])
        dimensions.append({"source_stroke": index, "width_mm": width, "height_mm": height})
    audit.check("four_checkboxes_remain_square", square,
                {"expected_side_mm": 5.*ART_SCALE, "measured": dimensions,
                 "mapping": "Uniform centered fit preserves artwork proportions."})

    ink_points = [p for segment in ink for p in segment]
    audit.check("ink_inside_requested_viewport", all(inside(p, VIEWPORT) for p in ink_points), VIEWPORT)
    audit.check("ink_has_10mm_a5_margin", all(inside(p, (PAPER[0]+10, PAPER[1]+10,
                                                     PAPER[2]-10, PAPER[3]-10)) for p in ink_points),
                "Independently derived from 210x148 paper and the 190x128 working area.")
    rows = list(csv.DictReader(io.StringIO(data["simulation/trajectory.csv"].decode("utf-8"))))
    csv_match = len(rows) == len(moves)
    for saved, move in zip(rows, moves):
        csv_match &= int(saved["line"]) == move["line"] and int(saved["drawing"]) == int(move["drawing"])
        csv_match &= all(close(float(saved[k]), v, 1e-7) for k, v in zip(
            ("x0", "y0", "z0", "x1", "y1", "z1"), (*move["start"], *move["end"])))
        csv_match &= close(float(saved["feed_mm_min"]), move["feed"], 1e-8)
        csv_match &= close(float(saved["duration_s"]), move["duration"], 1e-7)
    audit.check("independent_csv_replay", csv_match, "Every position, line, drawing flag, feed and duration agrees.")
    audit.metrics.update({
        "linear_moves": len(moves), "drawing_segments": len(ink), "strokes": strokes,
        "artwork_uniform_scale_mm_per_unit": ART_SCALE, "checkbox_dimensions_mm": dimensions,
        "ink_bounds_mm": [min(p[0] for p in ink_points), min(p[1] for p in ink_points),
                          max(p[0] for p in ink_points), max(p[1] for p in ink_points)],
        "ink_length_mm": sum(math.dist(a, b) for a, b in ink),
        "pen_up_xy_mm": sum(math.dist(m["start"][:2], m["end"][:2]) for m in travel),
        "ideal_feed_seconds": sum(m["duration"] for m in moves),
        "paper_bounds_mm": PAPER, "working_viewport_mm": VIEWPORT,
    })
    return moves


def check_geometry(data, audit, baseline=None):
    import cadquery as cq
    import trimesh
    from PIL import Image

    with tempfile.TemporaryDirectory(prefix="hs-a5-delivery-audit-") as directory:
        directory = Path(directory)

        def materialize(name):
            target = directory / Path(name).name
            target.write_bytes(data[name])
            return target

        shapes = {}
        for name in ("pen_adapter", "pen_clamp", "hotend_parking_plate"):
            shape = cq.importers.importStep(str(materialize("exports/"+name+".step"))).val()
            mesh = trimesh.load_mesh(materialize("exports/"+name+".stl"), process=True)
            shapes[name] = shape
            audit.check(name+"_solid_and_mesh", shape.isValid() and len(shape.Solids()) == 1
                        and shape.Volume() > 0 and mesh.is_watertight and mesh.is_winding_consistent
                        and mesh.volume > 0 and abs(shape.Volume()-mesh.volume)/shape.Volume() < .003,
                        "Actual STEP/STL reopened; closed solid and mesh volumes agree within 0.3%.")

        def cylinders(shape, direction, radius):
            result = []
            for face in shape.Faces():
                if face.geomType() == "CYLINDER":
                    cylinder = face._geomAdaptor().Cylinder()
                    axis = cylinder.Axis()
                    if abs(axis.Direction().Coord()[direction]) > .999 and close(cylinder.Radius(), radius, CAD_TOL):
                        result.append((axis.Location().Coord(), face.BoundingBox()))
            return result

        vendor = cq.importers.importStep(str(materialize("sources/E plate.step"))).val()
        for name, shape, radius in (("source", vendor, 1.5), ("adapter", shapes["pen_adapter"], 1.7)):
            holes = cylinders(shape, 2, radius)
            audit.check(name+"_retained_14mm_mount",
                        all(any(close(location[0], x, CAD_TOL) and close(location[1], 7.55, CAD_TOL)
                                for location, bounds in holes) for x in (9.5, 23.5)),
                        "Both source-defined M3 mount axes independently found in the delivered CAD.")
        for name, axis_z in (("pen_adapter", 32.0), ("pen_clamp", 32.4)):
            bores = cylinders(shapes[name], 1, 6.6)
            audit.check(name+"_12mm_pen_bore", any(close(p[0], 16.5, CAD_TOL)
                        and close(p[2], axis_z, CAD_TOL) for p, bounds in bores),
                        "6.6 mm bore radius = 12 mm pen plus documented 1.2 mm diametric liner allowance.")

        if baseline is not None:
            for name in ("pen_adapter", "pen_clamp"):
                path = directory / ("baseline_"+name+".step")
                path.write_bytes(baseline["exports/"+name+".step"])
                previous = cq.importers.importStep(str(path)).val()
                audit.check(name+"_actual_bore_revision",
                            bool(cylinders(previous, 1, 5.6))
                            and not cylinders(previous, 1, 6.6)
                            and bool(cylinders(shapes[name], 1, 6.6))
                            and not cylinders(shapes[name], 1, 5.6),
                            "Reopened baseline and final solids change the grip bore radius from 5.6 to 6.6 mm.")

        gap = shapes["pen_clamp"].BoundingBox().zmin - shapes["pen_adapter"].BoundingBox().zmax
        audit.check("clamp_adjustment_gap", close(gap, .4, CAD_TOL), {"actual_mm": gap, "expected_mm": .4})
        interference = sum(shapes[n].intersect(vendor).Volume() for n in ("pen_adapter", "pen_clamp"))
        audit.check("detailed_carriage_interference", interference < .001, {"volume_mm3": interference})

        layout = cq.importers.importStep(str(materialize("exports/plotter.step"))).val()
        paper_solids = []
        for solid in layout.Solids():
            b = solid.BoundingBox()
            if same_points([(b.xmin, b.ymin, b.zmin), (b.xmax, b.ymax, b.zmax)],
                           [(12.5, 43.5, 0), (222.5, 191.5, .1)]) and close(solid.Volume(), 3108., .01):
                paper_solids.append(solid)
        audit.check("step_contains_actual_a5_paper", len(paper_solids) == 1,
                    {"matching_solids": len(paper_solids), "expected_mm": [210, 148, .1]})
        scene = trimesh.load(materialize("exports/plotter.glb"), force="scene")
        papers = []
        for node in scene.graph.nodes_geometry:
            transform, geometry = scene.graph[node]
            if "paper" in (str(node)+" "+str(geometry)).lower():
                mesh = scene.geometry[geometry].copy()
                mesh.apply_transform(transform)
                papers.append(mesh.bounds.tolist())
        audit.check("glb_contains_actual_a5_paper", len(papers) == 1 and
                    same_points(papers[0], [(12.5, 43.5, 0), (222.5, 191.5, .1)]),
                    {"world_bounds_mm": papers})
        volume = float(scene.to_geometry().volume)
        audit.check("layout_step_glb_agree", layout.isValid() and len(layout.Solids()) >= 20
                    and abs(volume-layout.Volume())/layout.Volume() < .003,
                    "Full assembly and independent world-space GLB volume agree within 0.3%.")
        audit.check("reference_envelopes_remain_labeled",
                    sum("REFERENCE_ENVELOPE" in str(n) for n in scene.geometry) >= 15,
                    "Simplified retained parts remain visibly identified as reference envelopes.")
        for name in ("exports/device_render.png", "simulation/plotted_drawing.png"):
            with Image.open(io.BytesIO(data[name])) as image:
                size = image.size
                image.verify()
            audit.check("image_decodes_"+name, min(size) >= 400, {"pixel_size": size,
                        "semantic_visual_review": "Separate human/visual inspection is still required."})
        audit.metrics.update({"clamp_gap_mm": gap, "carriage_intersection_mm3": interference,
                              "mount_pitch_mm": 14., "requested_pen_bore_radius_mm": 6.6})


def render_preview(moves, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax in axes:
        ax.add_patch(Rectangle((0, 0), BED, BED, facecolor="#dce3e8", edgecolor="#9aa8b3"))
        ax.add_patch(Rectangle(PAPER[:2], 210, 148, facecolor="#fffef7", edgecolor="#20384a"))
        ax.add_patch(Rectangle(VIEWPORT[:2], 190, 128, fill=False, linestyle="--",
                               linewidth=.7, edgecolor="#b58d51"))
        for move in moves:
            a, b = move["start"], move["end"]
            if move["drawing"]:
                ax.plot([a[0], b[0]], [a[1]+OFFSET[1], b[1]+OFFSET[1]], color="#123c54", linewidth=.8)
        ax.set_aspect("equal")
        ax.set_xlabel("Pen-tip X (mm)")
        ax.set_ylabel("Pen-tip Y (mm)")
    axes[0].set(xlim=(-3, 238), ylim=(-3, 238), title="Independently decoded motion on the 235 mm bed")
    axes[1].set(xlim=(9, 226), ylim=(40, 195), title="Actual A5 card · dashed line is the 10 mm margin")
    fig.suptitle("A5 inspection card · delivered G-code replay · digital evidence only")
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--png", type=Path)
    parser.add_argument("--baseline", type=Path, help="Earlier exported study; verify retained artwork and actual bore revision.")
    args = parser.parse_args()
    audit, moves = Audit(), None
    try:
        data = inspect_archive(args.study, audit)
        baseline = inspect_archive(args.baseline, audit, "baseline_") if args.baseline else None
        if baseline is not None:
            earlier = read_json(baseline["requirements.json"])
            expected_baseline = {**EXPECTED, "drawing_width_mm": 100., "drawing_height_mm": 80.,
                                 "paper_width_mm": 180., "paper_height_mm": 180., "pen_diameter_mm": 10.}
            audit.check("baseline_requested_dimensions", earlier == expected_baseline,
                        {"expected": expected_baseline, "delivered": earlier})
            audit.check("revision_retains_exact_artwork",
                        baseline["sources/prompt-drawing.json"] == data["sources/prompt-drawing.json"],
                        "Archived drawing-source bytes are identical across the actual baseline and final revision.")
            previous_seal = read_json(baseline["study-verification.json"])
            previous_hashes = previous_seal.get("artifact_sha256", {})
            audit.check("baseline_sealed_bytes", previous_seal.get("artifact_integrity") is True
                        and previous_seal.get("summary", {}).get("requirements_met") is True
                        and set(previous_hashes) == set(baseline)-{"study-verification.json"}
                        and all(hashlib.sha256(baseline[n]).hexdigest() == h for n, h in previous_hashes.items()),
                        "The earlier completed study is a sealed output, not an invented comparison fixture.")

        check_contract(data, audit)
        moves = check_motion(data, audit)
        check_geometry(data, audit, baseline)
        if args.png:
            render_preview(moves, args.png)
    except Exception as exc:
        audit.check("audit_exception", False, type(exc).__name__+": "+str(exc))
    passed = bool(audit.checks) and all(c["passed"] for c in audit.checks)
    result = {
        "schema": "hardware_splicer.a5_independent_delivery_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "study": str(args.study), "study_sha256": hashlib.sha256(args.study.read_bytes()).hexdigest(),
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "baseline_sha256": hashlib.sha256(args.baseline.read_bytes()).hexdigest() if args.baseline else None,
        "accepted": passed, "expected_requirements": EXPECTED,
        "physical_validation_performed": False, "checks": audit.checks, "metrics": audit.metrics,
        "scope": "Independent archive, source-artwork, strict G-code, CSV, STEP/STL/GLB and A5-brief audit; no packaged code executed.",
        "limitations": ["Card wording and visual legibility need a separate visual review.",
                        "No physical printer, mounting, pen force, homing, powered movement or actual plotting was tested.",
                        "Travel duration is the ideal feed estimate, excluding acceleration and settling."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"accepted": passed, "checks": len(audit.checks),
                      "failed": [c for c in audit.checks if not c["passed"]],
                      "output": str(args.output)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
