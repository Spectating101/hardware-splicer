"""Isolated CadQuery/OCCT worker for pairwise STEP solid-interference evidence.

This module is intentionally executed as a subprocess. It is not imported by the API
process, so the optional CadQuery dependency remains optional for the base install.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


WORKER_SCHEMA = "hardware_splicer.cadquery_brep_worker.v1"
ROTATION_CONVENTION = "Rz*Ry*Rx; canonical STEP XYZ"


def _content_hash(path: str) -> str:
    return f"sha256:{hashlib.sha256(Path(path).read_bytes()).hexdigest()}"


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
    first_path = str(request["first_step_path"])
    second_path = str(request["second_step_path"])
    first_content_hash = _content_hash(first_path)
    second_content_hash = _content_hash(second_path)
    first = _place(_load_shape(cq, first_path), request["first_placement"])
    second = _place(_load_shape(cq, second_path), request["second_placement"])

    first_valid = bool(first.isValid())
    second_valid = bool(second.isValid())
    minimum_distance_mm = float(first.distance(second))
    intersection = first.intersect(second)
    intersection_volume_mm3 = max(0.0, float(intersection.Volume()))

    print(
        json.dumps(
            {
                "schema_version": WORKER_SCHEMA,
                "ok": True,
                "kernel": "cadquery_occt",
                "cadquery_version": getattr(cq, "__version__", None),
                "first_content_hash": first_content_hash,
                "second_content_hash": second_content_hash,
                "first_shape_valid": first_valid,
                "second_shape_valid": second_valid,
                "first_solid_count": len(first.Solids()),
                "second_solid_count": len(second.Solids()),
                "minimum_distance_mm": minimum_distance_mm,
                "intersection_volume_mm3": intersection_volume_mm3,
                "rotation_convention": ROTATION_CONVENTION,
            }
        )
    )


if __name__ == "__main__":
    main()