from __future__ import annotations

from typing import Any, Dict

from ..spec import ProjectSpec


def synthesize_control_profile(project: ProjectSpec) -> Dict[str, Any]:
    """
    Emit starter control/config recommendations for rapid implementation.
    """
    profile: Dict[str, Any] = {"controller_hz": 100, "loops": [], "notes": []}

    if project.linear_axis is not None:
        ax = project.linear_axis
        profile["loops"].append(
            {
                "name": "linear_axis_stepper",
                "type": "position",
                "max_speed_mm_s": round(ax.target_speed_mm_s, 1),
                "max_accel_mm_s2": round(ax.target_accel_mm_s2, 1),
                "microsteps": 16,
                "suggested_driver_current_a": 1.0,
            }
        )
        profile["notes"].append("Start with conservative accel; increase after missed-step test.")

    if project.leadscrew_axis is not None:
        ax = project.leadscrew_axis
        profile["loops"].append(
            {
                "name": "leadscrew_stepper",
                "type": "position",
                "max_speed_mm_s": round(ax.target_speed_mm_s, 1),
                "max_accel_mm_s2": round(ax.target_accel_mm_s2, 1),
                "lead_mm_per_rev": ax.lead_mm_per_rev,
                "microsteps": 16,
            }
        )

    if project.pan_tilt is not None:
        profile["loops"].append({"name": "pan_servo", "type": "angle", "min_deg": -85, "max_deg": 85, "update_hz": 50})
        profile["loops"].append({"name": "tilt_servo", "type": "angle", "min_deg": -60, "max_deg": 60, "update_hz": 50})

    if project.gripper is not None:
        profile["loops"].append({"name": "gripper_servo", "type": "position", "open_deg": 10, "close_deg": 85, "update_hz": 50})

    if not profile["loops"]:
        profile["notes"].append("No active motion subsystems detected; control profile is minimal.")

    return profile
