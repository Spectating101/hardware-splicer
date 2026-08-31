"""Isolated CadQuery/OCCT worker for adaptive mating-path transition brackets.

The worker imports each STEP source once, keeps one member fixed, and adaptively
bisects only coarse sampled intervals whose boolean geometry predicate changes.
It returns bounded predicate-change brackets. It does not claim a unique physical
contact point, monotonicity inside a bracket, continuous-path clearance, connector
mating, or whole-assembly validity.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path


WORKER_SCHEMA = "hardware_splicer.cadquery_brep_transition_refinement_worker.v1"
ROTATION_CONVENTION = "Rz*Ry*Rx; canonical STEP XYZ"
ROTATION_MATCH_TOLERANCE_DEG = 1e-9
MAX_REFINEMENT_EVALUATIONS = 256


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


def _place(shape, translation, rotation):
    values = [float(value) for value in translation]
    angles = [float(value) for value in rotation]
    if len(values) != 3 or len(angles) != 3:
        raise RuntimeError("CadQuery placement requires three translation and three rotation values")
    return shape.moved(
        x=values[0],
        y=values[1],
        z=values[2],
        rx=angles[0],
        ry=angles[1],
        rz=angles[2],
    )


def _interpolate(start, end, fraction: float):
    return [
        float(start[index]) + fraction * (float(end[index]) - float(start[index]))
        for index in range(3)
    ]


def _metrics(moving_base, fixed, start_translation, end_translation, rotation, fraction: float):
    moving = _place(
        moving_base,
        _interpolate(start_translation, end_translation, fraction),
        rotation,
    )
    distance = float(moving.distance(fixed))
    intersection = moving.intersect(fixed)
    volume = max(0.0, float(intersection.Volume()))
    if not math.isfinite(distance) or distance < 0.0:
        raise RuntimeError("OCCT returned an invalid minimum distance")
    if not math.isfinite(volume) or volume < 0.0:
        raise RuntimeError("OCCT returned an invalid intersection volume")
    return distance, volume


def _state(distance: float, volume: float, contact_tolerance: float, volume_tolerance: float) -> str:
    if volume > volume_tolerance:
        return "interference"
    if distance <= contact_tolerance + 1e-12:
        return "contact"
    return "clear"


def _predicate(kind: str, state: str) -> bool:
    if kind == "clearance_boundary":
        return state == "clear"
    if kind == "interference_boundary":
        return state == "interference"
    raise RuntimeError(f"unsupported refinement boundary kind: {kind}")


def main() -> None:
    if len(sys.argv) != 2:
        raise RuntimeError("CadQuery BREP transition refinement worker requires one JSON input path")

    import cadquery as cq  # Optional specialist dependency; worker process only.

    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    moving_path = str(request["moving_step_path"])
    fixed_path = str(request["fixed_step_path"])
    moving_base = _load_shape(cq, moving_path)

    fixed_row = dict(request["fixed_placement"])
    fixed = _place(
        _load_shape(cq, fixed_path),
        fixed_row["translation_mm"],
        fixed_row["rotation_deg_xyz"],
    )
    start = dict(request["moving_start_placement"])
    end = dict(request["moving_end_placement"])
    start_translation = list(start["translation_mm"])
    end_translation = list(end["translation_mm"])
    rotation = [float(value) for value in start["rotation_deg_xyz"]]
    end_rotation = [float(value) for value in end["rotation_deg_xyz"]]
    if any(
        abs(start_value - end_value) > ROTATION_MATCH_TOLERANCE_DEG
        for start_value, end_value in zip(rotation, end_rotation)
    ):
        raise RuntimeError("transition refinement requires translation-only matching rotations")

    contact_tolerance = float(request["contact_distance_tolerance_mm"])
    volume_tolerance = float(request["intersection_volume_tolerance_mm3"])
    fraction_tolerance = float(request["refinement_fraction_tolerance"])
    max_depth = int(request["refinement_max_depth"])
    candidates = list(request["candidates"])
    worst_case_evaluations = len(candidates) * (max_depth + 2)
    if worst_case_evaluations > MAX_REFINEMENT_EVALUATIONS:
        raise RuntimeError(
            "adaptive transition refinement worst-case exact evaluation count "
            f"{worst_case_evaluations} exceeds bounded worker budget {MAX_REFINEMENT_EVALUATIONS}"
        )

    brackets = []
    evaluation_count = 0
    for boundary_index, candidate in enumerate(candidates):
        kind = str(candidate["kind"])
        low_fraction = float(candidate["lower_fraction"])
        high_fraction = float(candidate["upper_fraction"])
        if not 0.0 <= low_fraction < high_fraction <= 1.0:
            raise RuntimeError("refinement candidate fractions must be ordered inside [0, 1]")

        low_distance, low_volume = _metrics(
            moving_base, fixed, start_translation, end_translation, rotation, low_fraction
        )
        high_distance, high_volume = _metrics(
            moving_base, fixed, start_translation, end_translation, rotation, high_fraction
        )
        evaluation_count += 2
        low_state = _state(low_distance, low_volume, contact_tolerance, volume_tolerance)
        high_state = _state(high_distance, high_volume, contact_tolerance, volume_tolerance)
        low_predicate = _predicate(kind, low_state)
        high_predicate = _predicate(kind, high_state)
        if low_predicate == high_predicate:
            raise RuntimeError(
                f"refinement candidate {boundary_index} no longer brackets a {kind} predicate change"
            )

        depth = 0
        while depth < max_depth and (high_fraction - low_fraction) > fraction_tolerance:
            mid_fraction = (low_fraction + high_fraction) / 2.0
            mid_distance, mid_volume = _metrics(
                moving_base, fixed, start_translation, end_translation, rotation, mid_fraction
            )
            evaluation_count += 1
            mid_state = _state(mid_distance, mid_volume, contact_tolerance, volume_tolerance)
            mid_predicate = _predicate(kind, mid_state)
            if mid_predicate == low_predicate:
                low_fraction = mid_fraction
                low_distance = mid_distance
                low_volume = mid_volume
                low_state = mid_state
            else:
                high_fraction = mid_fraction
                high_distance = mid_distance
                high_volume = mid_volume
                high_state = mid_state
            depth += 1

        brackets.append(
            {
                "boundary_index": boundary_index,
                "kind": kind,
                "lower_fraction": low_fraction,
                "upper_fraction": high_fraction,
                "lower_state": low_state,
                "upper_state": high_state,
                "lower_minimum_distance_mm": low_distance,
                "upper_minimum_distance_mm": high_distance,
                "lower_intersection_volume_mm3": low_volume,
                "upper_intersection_volume_mm3": high_volume,
                "refinement_depth": depth,
                "evaluation_count": depth + 2,
                "converged": (high_fraction - low_fraction) <= fraction_tolerance,
                "max_depth_reached": depth >= max_depth and (high_fraction - low_fraction) > fraction_tolerance,
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
                "moving_shape_valid": bool(moving_base.isValid()),
                "fixed_shape_valid": bool(fixed.isValid()),
                "moving_solid_count": len(moving_base.Solids()),
                "fixed_solid_count": len(fixed.Solids()),
                "rotation_convention": ROTATION_CONVENTION,
                "evaluation_budget": MAX_REFINEMENT_EVALUATIONS,
                "evaluation_count": evaluation_count,
                "brackets": brackets,
            }
        )
    )


if __name__ == "__main__":
    main()
