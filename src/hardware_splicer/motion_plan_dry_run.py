"""Simulation-only validator for registered robot/workcell motion-plan artifacts.

The validator accepts a narrow JSON trajectory schema and checks joint identity,
position limits, monotonic timing and configured velocity limits. It never
connects to ROS or a robot controller and always refuses to claim live-readiness.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Mapping

from .fabrication_operator import FabricationValidationError
from .physical_artifact import PhysicalArtifactRegistry


@dataclass(frozen=True)
class JointLimit:
    min_position: float
    max_position: float
    max_velocity: float | None = None

    def validate(self, name: str) -> None:
        if not _finite(self.min_position) or not _finite(self.max_position) or self.min_position > self.max_position:
            raise FabricationValidationError(f"joint {name!r} position limits are invalid")
        if self.max_velocity is not None and (not _finite(self.max_velocity) or self.max_velocity <= 0):
            raise FabricationValidationError(f"joint {name!r} max_velocity must be positive")


class MotionPlanDryRun:
    def __init__(self, *, artifacts: PhysicalArtifactRegistry, joint_limits: Mapping[str, JointLimit]):
        if not isinstance(joint_limits, Mapping) or not joint_limits:
            raise FabricationValidationError("motion-plan validator requires joint limits")
        clean: dict[str, JointLimit] = {}
        for name, limit in joint_limits.items():
            if not isinstance(name, str) or not name.strip() or len(name.strip()) > 128:
                raise FabricationValidationError("joint names must be bounded text")
            if not isinstance(limit, JointLimit):
                raise FabricationValidationError("joint limits must use JointLimit")
            limit.validate(name.strip())
            clean[name.strip()] = limit
        self.artifacts = artifacts
        self.joint_limits = clean

    def analyze(self, artifact_id: str) -> dict[str, Any]:
        descriptor = self.artifacts.describe(artifact_id)
        if descriptor.get("kind") != "motion_plan":
            raise FabricationValidationError("motion-plan dry-run requires a motion_plan artifact")
        raw = self.artifacts.bytes(artifact_id)
        if len(raw) > 8 * 1024 * 1024:
            raise FabricationValidationError("motion plan exceeds dry-run size limit")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FabricationValidationError("motion plan must be UTF-8 JSON") from exc
        if not isinstance(value, Mapping):
            raise FabricationValidationError("motion plan root must be an object")
        joints = value.get("joints")
        points = value.get("points")
        if not isinstance(joints, list) or not joints or any(not isinstance(item, str) or not item for item in joints):
            raise FabricationValidationError("motion plan joints must be a non-empty string list")
        if len(joints) != len(set(joints)):
            raise FabricationValidationError("motion plan joint names must be unique")
        unknown = [name for name in joints if name not in self.joint_limits]
        if unknown:
            raise FabricationValidationError("motion plan contains unconfigured joints: " + ", ".join(unknown))
        if not isinstance(points, list) or len(points) < 1 or len(points) > 100000:
            raise FabricationValidationError("motion plan points must contain 1..100000 entries")

        blockers: list[dict[str, Any]] = []
        previous_time: float | None = None
        previous_positions: dict[str, float] | None = None
        duration = 0.0
        for index, point in enumerate(points):
            if not isinstance(point, Mapping):
                raise FabricationValidationError("motion plan point must be an object")
            time_s = point.get("time_s")
            positions = point.get("positions")
            if not _finite(time_s) or float(time_s) < 0:
                raise FabricationValidationError("motion plan time_s must be finite and non-negative")
            t = float(time_s)
            if previous_time is not None and t <= previous_time:
                blockers.append({"point": index, "type": "non_monotonic_time", "time_s": t})
            if not isinstance(positions, Mapping) or set(positions) != set(joints):
                raise FabricationValidationError("each motion point must contain exactly the declared joints")
            normalized: dict[str, float] = {}
            for joint in joints:
                raw_position = positions[joint]
                if not _finite(raw_position):
                    raise FabricationValidationError("joint position must be finite")
                position = float(raw_position)
                normalized[joint] = position
                limit = self.joint_limits[joint]
                if position < limit.min_position or position > limit.max_position:
                    blockers.append({
                        "point": index,
                        "type": "position_limit",
                        "joint": joint,
                        "position": position,
                        "allowed": [limit.min_position, limit.max_position],
                    })
                if previous_time is not None and previous_positions is not None and t > previous_time and limit.max_velocity is not None:
                    velocity = abs(position - previous_positions[joint]) / (t - previous_time)
                    if velocity > limit.max_velocity:
                        blockers.append({
                            "point": index,
                            "type": "velocity_limit",
                            "joint": joint,
                            "velocity": velocity,
                            "allowed_max": limit.max_velocity,
                        })
            previous_time = t
            previous_positions = normalized
            duration = max(duration, t)

        return {
            "schema": "hardware_splicer.motion_plan_dry_run.v1",
            "artifact_id": descriptor["artifact_id"],
            "artifact_sha256": descriptor["sha256"],
            "joint_count": len(joints),
            "point_count": len(points),
            "duration_s": duration,
            "blockers": blockers,
            "simulation_only": True,
            "ready_for_live_execution": False,
            "live_execution_blockers": [
                "dry-run validator never grants live robot execution",
                *(["joint/timing limits violated"] if blockers else []),
            ],
            "physical_correctness": "UNPROVEN",
        }


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
