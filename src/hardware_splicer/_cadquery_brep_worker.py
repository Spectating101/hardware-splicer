"""Isolated CadQuery/OCCT worker for pairwise STEP solid-interference evidence.

This module is intentionally executed as a subprocess. It is not imported by the API
process, so the optional CadQuery dependency remains optional for the base install.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_shape(cq, path: str):
    workplane = cq.importers.importStep(path)
    shapes = [value for value in workplane.vals() if hasattr(value, "wrapped")]
    if not shapes:
        raise RuntimeError(f"STEP import produced no CadQuery shapes: {path}")
    if len(shapes) == 1:
        return shapes[0]
    return cq.Compound.makeCompound(shapes)


def _place(shape, row: dict):
    translation = [float(value) for value in row.get("translation_mm", [0.0, 0.0, 0.0])]
    rotation = [float(value) for value in row.get("rotation_deg_xyz", [0.0, 0.0, 0.0])]
    if len(translation) != 3 or len(rotation) != 3:
        raise RuntimeError("CadQuery placement requires three translation and three rotation values")
    return shape.moved(
        x=translation[0],
        y=translation[1],
        z=translation[2],
        rx=rotation[0],
        ry=rotation[1],
        rz=rotation[2],
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise RuntimeError("CadQuery BREP worker requires one JSON input path")

    import cadquery as cq  # Optional specialist dependency; worker process only.

    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    first = _place(_load_shape(cq, request["first_step_path"]), request["first_placement"])
    second = _place(_load_shape(cq, request["second_step_path"]), request["second_placement"])

    first_valid = bool(first.isValid())
    second_valid = bool(second.isValid())
    minimum_distance_mm = float(first.distance(second))
    intersection = first.intersect(second)
    intersection_volume_mm3 = max(0.0, float(intersection.Volume()))

    print(
        json.dumps(
            {
                "ok": True,
                "kernel": "cadquery_occt",
                "cadquery_version": getattr(cq, "__version__", None),
                "first_shape_valid": first_valid,
                "second_shape_valid": second_valid,
                "first_solid_count": len(first.Solids()),
                "second_solid_count": len(second.Solids()),
                "minimum_distance_mm": minimum_distance_mm,
                "intersection_volume_mm3": intersection_volume_mm3,
                "rotation_convention": "Rz*Ry*Rx; canonical STEP XYZ",
            }
        )
    )


if __name__ == "__main__":
    main()
