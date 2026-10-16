"""Simulation-only G-code analysis for CNC/laser machine-job artifacts.

This module never opens a device or emits machine commands. It parses a narrow
linear-motion subset to estimate bounds and flags hazardous/opaque constructs.
Unknown semantics are blockers for live execution rather than silently accepted.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from .fabrication_operator import FabricationValidationError
from .physical_artifact import PhysicalArtifactRegistry

_TOKEN_RE = re.compile(r"([A-Za-z])\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))")
_PAREN_COMMENT_RE = re.compile(r"\([^)]*\)")


@dataclass(frozen=True)
class MachineEnvelope:
    min_x_mm: float
    max_x_mm: float
    min_y_mm: float
    max_y_mm: float
    min_z_mm: float
    max_z_mm: float
    max_feed_mm_min: float | None = None

    def validate(self) -> None:
        for low, high, label in (
            (self.min_x_mm, self.max_x_mm, "x"),
            (self.min_y_mm, self.max_y_mm, "y"),
            (self.min_z_mm, self.max_z_mm, "z"),
        ):
            if not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                for value in (low, high)
            ):
                raise FabricationValidationError(f"machine {label} envelope must be finite")
            if float(low) > float(high):
                raise FabricationValidationError(f"machine {label} envelope is inverted")
        if self.max_feed_mm_min is not None:
            if (
                not isinstance(self.max_feed_mm_min, (int, float))
                or isinstance(self.max_feed_mm_min, bool)
                or not math.isfinite(float(self.max_feed_mm_min))
                or self.max_feed_mm_min <= 0
            ):
                raise FabricationValidationError("machine max feed must be a positive finite number")


class GcodeDryRunAnalyzer:
    def __init__(self, *, artifacts: PhysicalArtifactRegistry, envelope: MachineEnvelope):
        envelope.validate()
        self.artifacts = artifacts
        self.envelope = envelope

    def analyze(self, artifact_id: str) -> dict[str, Any]:
        descriptor = self.artifacts.describe(artifact_id)
        if descriptor.get("kind") != "machine_job":
            raise FabricationValidationError("G-code dry-run requires a machine_job artifact")
        data = self.artifacts.bytes(artifact_id)
        if len(data) > 16 * 1024 * 1024:
            raise FabricationValidationError("machine job is too large for dry-run analysis")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = data.decode("ascii")
            except UnicodeDecodeError as exc:
                raise FabricationValidationError("machine job must be textual G-code") from exc

        position = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        mins = dict(position)
        maxs = dict(position)
        unit_scale = 1.0
        absolute = True
        modal_motion: int | None = None
        motion_lines = 0
        max_feed = 0.0
        hazards: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []

        for line_number, raw in enumerate(text.splitlines(), start=1):
            line = _PAREN_COMMENT_RE.sub("", raw).split(";", 1)[0].strip()
            if not line:
                continue
            upper = line.upper()
            if any(marker in upper for marker in ("#", "[", "]")) or re.search(r"(^|\s)O\d+", upper):
                blockers.append({"line": line_number, "type": "opaque_macro_or_expression", "text": line[:200]})
                modal_motion = None
                continue
            tokens = [(letter.upper(), float(number)) for letter, number in _TOKEN_RE.findall(line)]
            if not tokens:
                blockers.append({"line": line_number, "type": "unparsed_line", "text": line[:200]})
                modal_motion = None
                continue

            non_integer_control = [
                f"{letter}{value:g}"
                for letter, value in tokens
                if letter in {"G", "M"} and not float(value).is_integer()
            ]
            if non_integer_control:
                blockers.append({
                    "line": line_number,
                    "type": "non_integer_or_unsupported_control_code",
                    "codes": non_integer_control,
                })
                modal_motion = None
                continue

            g_codes = [int(value) for letter, value in tokens if letter == "G"]
            m_codes = [int(value) for letter, value in tokens if letter == "M"]
            for code in m_codes:
                if code in {3, 4, 6, 7, 8}:
                    hazards.append({"line": line_number, "code": f"M{code}", "text": line[:200]})
                elif code in {98, 99}:
                    blockers.append({"line": line_number, "type": "opaque_subprogram_control", "code": f"M{code}"})
                elif code not in {2, 5, 30}:
                    blockers.append({"line": line_number, "type": "unsupported_m_code", "code": f"M{code}"})

            if 20 in g_codes:
                unit_scale = 25.4
            if 21 in g_codes:
                unit_scale = 1.0
            if 90 in g_codes:
                absolute = True
            if 91 in g_codes:
                absolute = False

            unsupported_motion = [code for code in g_codes if code in {2, 3, 38, 81, 82, 83, 84, 85, 86, 87, 88, 89}]
            if unsupported_motion:
                blockers.append({
                    "line": line_number,
                    "type": "unsupported_motion_semantics",
                    "codes": [f"G{code}" for code in unsupported_motion],
                })
                modal_motion = None
                continue

            unknown_g = [
                code
                for code in g_codes
                if code not in {0, 1, 4, 17, 18, 19, 20, 21, 40, 49, 54, 55, 56, 57, 58, 59, 80, 90, 91, 94}
            ]
            if unknown_g:
                blockers.append({"line": line_number, "type": "unsupported_g_code", "codes": [f"G{code}" for code in unknown_g]})
                modal_motion = None
                continue

            if 0 in g_codes:
                modal_motion = 0
            if 1 in g_codes:
                modal_motion = 1

            feed_values = [value * unit_scale for letter, value in tokens if letter == "F"]
            if feed_values:
                max_feed = max(max_feed, max(feed_values))

            axis_words = {
                axis: [value * unit_scale for letter, value in tokens if letter == axis]
                for axis in ("X", "Y", "Z")
            }
            has_axes = any(axis_words[axis] for axis in axis_words)
            if not has_axes:
                continue
            if modal_motion not in {0, 1}:
                blockers.append({
                    "line": line_number,
                    "type": "coordinate_words_without_supported_motion_mode",
                    "text": line[:200],
                })
                continue

            target = dict(position)
            for axis in ("X", "Y", "Z"):
                values = axis_words[axis]
                if not values:
                    continue
                value = values[-1]
                target[axis] = value if absolute else target[axis] + value
            motion_lines += 1
            position = target
            for axis in ("X", "Y", "Z"):
                mins[axis] = min(mins[axis], position[axis])
                maxs[axis] = max(maxs[axis], position[axis])

        envelope_violations = []
        ranges = {
            "X": (self.envelope.min_x_mm, self.envelope.max_x_mm),
            "Y": (self.envelope.min_y_mm, self.envelope.max_y_mm),
            "Z": (self.envelope.min_z_mm, self.envelope.max_z_mm),
        }
        for axis, (low, high) in ranges.items():
            if mins[axis] < low or maxs[axis] > high:
                envelope_violations.append({
                    "axis": axis,
                    "observed_min_mm": mins[axis],
                    "observed_max_mm": maxs[axis],
                    "allowed_min_mm": low,
                    "allowed_max_mm": high,
                })
        if self.envelope.max_feed_mm_min is not None and max_feed > self.envelope.max_feed_mm_min:
            envelope_violations.append({
                "axis": "feed",
                "observed_max_mm_min": max_feed,
                "allowed_max_mm_min": self.envelope.max_feed_mm_min,
            })

        return {
            "schema": "hardware_splicer.gcode_dry_run.v1",
            "artifact_id": descriptor["artifact_id"],
            "artifact_sha256": descriptor["sha256"],
            "dry_run_only": True,
            "motion_lines": motion_lines,
            "bounds_mm": {
                "x": [mins["X"], maxs["X"]],
                "y": [mins["Y"], maxs["Y"]],
                "z": [mins["Z"], maxs["Z"]],
            },
            "max_feed_mm_min": max_feed,
            "hazardous_commands": hazards,
            "unsupported_or_opaque": blockers,
            "envelope_violations": envelope_violations,
            "ready_for_live_execution": False,
            "live_execution_blockers": [
                "dry-run analyzer never grants live execution",
                *(["unsupported or opaque G-code present"] if blockers else []),
                *(["configured machine envelope exceeded"] if envelope_violations else []),
                *(["hazardous machine commands require machine-specific review"] if hazards else []),
            ],
            "physical_correctness": "UNPROVEN",
        }
