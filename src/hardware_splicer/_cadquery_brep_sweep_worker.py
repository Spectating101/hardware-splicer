"""Isolated CadQuery/OCCT worker for bounded sampled STEP mating-path evidence.

The worker imports the two STEP sources once, keeps one member fixed, and evaluates
one moving member at a bounded list of declared translation poses. It deliberately
returns per-sample exact BREP distance/intersection evidence only; continuity between
samples is not inferred here or by the product API.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


WORKER_SCHEMA = "hardware_splicer.cadquery_brep_sweep_worker.v1"
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
        raise RuntimeError("CadQuery BREP sweep worker requires one JSON input path")

    import cadquery as cq  # Optional specialist dependency; worker process only.

    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    moving_path = str(request["moving_step_path"])
    fixed_path = str(request["fixed_step_path"])
    moving_base = _load_shape(cq, moving_path)
    fixed = _place(_load_shape(cq, fixed_path), request["fixed_placement"])
    moving_placements = list(request["moving_placements"])
    if not moving_placements:
        raise RuntimeError("CadQuery BREP sweep requires at least one moving placement")

    moving_valid = bool(moving_base.isValid())
    fixed_valid = bool(fixed.isValid())
    samples = []
    for index, placement in enumerate(moving_placements):
        moving = _place(moving_base, placement)
        minimum_distance_mm = float(moving.distance(fixed))
        intersection = moving.intersect(fixed)
        intersection_volume_mm3 = max(0.0, float(intersection.Volume()))
        samples.append(
            {
                "sample_index": index,
                "minimum_distance_mm": minimum_distance_mm,
                "intersection_volume_mm3": intersection_volume_mm3,
            }
        )

    print(
        json.dumps(
            {
                "schema_version": WORKER_SCHEMA,
                "ok": True,
                "kernel": "cadquery_occt",
                "cadquery_version": getattr(cq, "__version__", None),
                "moving_content_hash": _content_hash(moving_path),
                "fixed_content_hash": _content_hash(fixed_path),
                "moving_shape_valid": moving_valid,
                "fixed_shape_valid": fixed_valid,
                "moving_solid_count": len(moving_base.Solids()),
                "fixed_solid_count": len(fixed.Solids()),
                "rotation_convention": ROTATION_CONVENTION,
                "samples": samples,
            }
        )
    )


if __name__ == "__main__":
    main()
