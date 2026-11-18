"""Generate an open parts tray in millimetres and check its exported STEP solid."""
import argparse
from math import isclose, isfinite
from pathlib import Path

import cadquery as cq


def make_tray(directory, width, depth, height, wall):
    if not all(isfinite(x) and x > 0 for x in (width, depth, height, wall)):
        raise ValueError("Tray dimensions and wall thickness must be finite and positive")
    if min(width, depth) <= 2 * wall or height <= wall:
        raise ValueError("Tray walls leave no cavity")
    model = (cq.Workplane("XY").box(width, depth, height, centered=(True, True, False))
             .faces(">Z").workplane().rect(width - 2 * wall, depth - 2 * wall)
             .cutBlind(wall - height))
    directory.mkdir(parents=True, exist_ok=True)
    step = directory / "parts_tray.step"
    cq.exporters.export(model, str(step))
    solid, = cq.importers.importStep(str(step)).solids().vals()
    box = solid.BoundingBox()
    measured = (box.xlen, box.ylen, box.zlen)
    volume = width * depth * height - (width - 2 * wall) * (depth - 2 * wall) * (height - wall)
    if (not solid.isValid() or not isclose(solid.Volume(), volume)
            or not all(isclose(actual, target) for actual, target in zip(measured, (width, depth, height)))):
        raise ValueError("Exported solid differs from the requested tray")
    cq.exporters.export(model, str(directory / "parts_tray.stl"))
    print(f"Checked STEP dimensions in mm: {box.xlen:g} × {box.ylen:g} × {box.zlen:g}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--width", type=float, default=245)
    parser.add_argument("--depth", type=float, default=205)
    parser.add_argument("--height", type=float, default=20)
    parser.add_argument("--wall", type=float, default=2, help="Wall and base thickness in mm")
    args = parser.parse_args()
    make_tray(args.directory, args.width, args.depth, args.height, args.wall)
