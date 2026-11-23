"""Build HS's horizontal inspection nest from pinned mounting-hole drawings. Units are mm."""

import argparse
from hashlib import sha256
import json
from math import dist
from pathlib import Path
from time import perf_counter
from urllib.parse import quote
from urllib.request import urlopen
from xml.etree import ElementTree as ET

import cadquery as cq

HERE = Path(__file__).resolve().parent
DOCK = [(-53, -31, 5), (49, 30, 3.5)]
BASE_H, PLATE_H, STAND_H = 4, 3, 6
PIN_GAP = 0.4  # diametral allowance at both removable interfaces


def read_board(profile, cache, fetch):
    source = profile["source"]
    file = cache / profile["file"]
    if not file.exists() and fetch:
        url = f"https://raw.githubusercontent.com/{source['repo']}/{source['revision']}/{quote(source['path'])}"
        with urlopen(url, timeout=45) as response:
            data = response.read()
    else:
        data = file.read_bytes()
    if sha256(data).hexdigest() != source["sha256"]:
        raise ValueError(f"Board file differs from pinned revision: {file.name}")
    if not file.exists():
        cache.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    board = ET.fromstring(data).find("drawing/board")
    elements = {e.get("name"): e for e in board.findall("elements/element")}
    packages = {
        (lib.get("name"), p.get("name")): p
        for lib in board.findall("libraries/library")
        for p in lib.findall("packages/package")
    }
    holes = []
    cx, cy = profile["board_center_mm"]
    for ref in profile["mount_refs"]:
        element = elements[ref]
        package = packages[element.get("library"), element.get("package")]
        (hole,) = package.findall("hole") + package.findall("pad")
        if float(hole.get("x")) or float(hole.get("y")):
            raise ValueError(f"Needs a footprint transform for {ref}")
        holes.append(
            (
                float(element.get("x")) - cx,
                float(element.get("y")) - cy,
                float(hole.get("drill")),
            )
        )
    if len(holes) != 4 or len(set((x, y) for x, y, _ in holes)) != 4:
        raise ValueError("Expected four distinct mounting holes")
    return holes


def plate(x, y, height):
    return (
        cq.Workplane("XY")
        .box(x, y, height, centered=(True, True, False))
        .edges("|Z")
        .fillet(2)
        .val()
    )


def cylinder(x, y, z, diameter, height):
    return cq.Solid.makeCylinder(diameter / 2, height, cq.Vector(x, y, z))


def make_base():
    base = plate(120, 76, BASE_H)
    for x, y, d in DOCK:
        base = base.fuse(cylinder(x, y, BASE_H, d, 2.5))
    return base.clean()


def make_carrier(holes):
    carrier = plate(116, 72, PLATE_H)
    for x, y, d in DOCK:
        carrier = carrier.cut(cylinder(x, y, -1, d + PIN_GAP, PLATE_H + 2))
    for x, y, diameter in holes:
        if not 2 <= diameter <= 4 or abs(x) > 54 or abs(y) > 32:
            raise ValueError("Hole outside the supported pin or plate dimensions")
        if any(dist((x, y), dock[:2]) < 6 for dock in DOCK):
            raise ValueError("Support overlaps the dock interface")
        carrier = carrier.fuse(cylinder(x, y, PLATE_H, 4.6, STAND_H))
        carrier = carrier.fuse(
            cylinder(x, y, PLATE_H + STAND_H, diameter - PIN_GAP, 1.5)
        )
    return carrier.clean()


def export_solid(solid, output, name):
    path = output / (name + ".step")
    cq.exporters.export(solid, str(path))
    cq.exporters.export(solid, str(output / (name + ".stl")))
    (reopened,) = cq.importers.importStep(str(path)).solids().vals()
    if not reopened.isValid():
        raise ValueError(f"Invalid STEP solid for {name}")
    return reopened


def check_fit(base, carrier, holes, envelope):
    # The test board is deliberately conservative in XY and omits all electronics.
    # It represents a 1.6 mm board for the insertion check only.
    z = BASE_H + PLATE_H + STAND_H
    board = (
        cq.Workplane("XY")
        .box(*envelope, 1.6, centered=(True, True, False))
        .val()
        .translate((0, 0, z))
    )
    for x, y, d in holes:
        board = board.cut(cylinder(x, y, z - 1, d, 4))
    seated = carrier.translate((0, 0, BASE_H))
    overlaps = [base.intersect(seated).Volume(), seated.intersect(board).Volume()]
    reversed_plate = seated.rotate((0, 0, 0), (0, 0, 1), 180)
    # Align both reversed hole centers with the opposite pins, giving a reversed
    # carrier its best chance to seat even if the operator shifts the plate.
    shift = (DOCK[0][0] + DOCK[1][0], DOCK[0][1] + DOCK[1][1], 0)
    reversed_overlap = base.intersect(reversed_plate.translate(shift)).Volume()
    # Check each exported pin and shoulder locally so a missing peg cannot pass a collision test.
    for x, y, d in holes:
        expected = cylinder(x, y, z, d - PIN_GAP, 1.5)
        shoulder = cylinder(x, y, z - 0.5, 4.6, 0.5)
        for gauge in (expected, shoulder):
            if gauge.cut(seated).Volume() > 1e-5:
                raise ValueError("Missing pin or support material at source datum")
    if max(overlaps) > 1e-5 or reversed_overlap < 1:
        raise ValueError("Invalid mating clearance or unkeyed carrier")
    return {
        "seated_intersections_mm3": [round(n, 6) for n in overlaps],
        "reversed_dock_intersection_mm3": round(reversed_overlap, 3),
    }


def build(cache, output, fetch, selected):
    profiles = json.loads((HERE / "boards.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    start = perf_counter()
    base = export_solid(make_base(), output, "dock")
    timings = {"dock": round(perf_counter() - start, 3)}
    results = {}
    for name in selected or profiles:
        start = perf_counter()
        profile = profiles[name]
        holes = read_board(profile, cache, fetch)
        carrier = export_solid(make_carrier(holes), output, name)
        check = check_fit(base, carrier, holes, profile["board_envelope_mm"])
        results[name] = {
            **check,
            "board_sha256": profile["source"]["sha256"],
            "reference_xy_and_drill_mm": [[round(v, 4) for v in h] for h in holes],
        }
        timings[name] = round(perf_counter() - start, 3)
    (output / "verification.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"elapsed_seconds": timings, "verified": list(results)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument(
        "--board",
        action="append",
        choices=json.loads((HERE / "boards.json").read_text()),
    )
    args = parser.parse_args()
    build(args.cache, args.output, args.fetch, args.board)
