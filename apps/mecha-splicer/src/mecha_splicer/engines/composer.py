from __future__ import annotations

from typing import Any, Dict, Tuple

from ..spec import ProjectSpec


def compose_project(project: ProjectSpec) -> Tuple[ProjectSpec, Dict[str, Any]]:
    """
    Intent-level auto composition.
    Adds missing sub-systems based on `system_goal.application`, but does not overwrite
    user-provided detailed specs.
    """
    if not project.auto_compose or project.system_goal is None:
        return project, {"applied": False, "reason": "auto_compose disabled or no system_goal"}

    goal = project.system_goal
    updates: Dict[str, Any] = {}
    decisions: list[str] = []

    if goal.application == "control_box":
        if project.enclosure is None:
            updates["enclosure"] = {
                "name": f"{project.project_name}_control_box",
                "inner_w_mm": max(100.0, goal.workspace_w_mm),
                "inner_d_mm": max(70.0, goal.workspace_h_mm),
                "inner_h_mm": 45.0 if goal.environment == "outdoor" else 35.0,
                "wall_mm": 3.0 if goal.environment == "outdoor" else 2.4,
                "lid_style": "screw",
            }
            decisions.append("Added default enclosure for control-box application.")

    elif goal.application == "pan_tilt_camera":
        if project.pan_tilt is None:
            servo = "mg996r" if goal.payload_kg > 0.4 else "sg90"
            updates["pan_tilt"] = {"name": f"{project.project_name}_pan_tilt", "pan_servo": servo, "tilt_servo": servo}
            decisions.append(f"Added pan/tilt module with {servo} servos based on payload.")
        if project.enclosure is None and project.electronics is None:
            updates["enclosure"] = {"name": f"{project.project_name}_controller_box", "inner_w_mm": 80.0, "inner_d_mm": 50.0, "inner_h_mm": 30.0}
            decisions.append("Added controller enclosure scaffold.")

    elif goal.application == "mobile_robot":
        if project.linear_axis is None:
            speed_mm_s = max(60.0, goal.target_speed_m_s * 1000.0 * 0.4)
            updates["linear_axis"] = {
                "name": f"{project.project_name}_axis",
                "travel_mm": max(120.0, goal.workspace_w_mm * 0.6),
                "rod_length_mm": max(220.0, goal.workspace_w_mm * 0.9),
                "target_speed_mm_s": speed_mm_s,
                "payload_n": max(8.0, goal.payload_kg * 9.81),
            }
            decisions.append("Added linear-axis module for motion subsystem.")
        if project.belt_reduction is None:
            updates["belt_reduction"] = {"name": f"{project.project_name}_drive_reduction", "motor_pulley_teeth": 20, "driven_pulley_teeth": 60}
            decisions.append("Added belt reduction stage for drivetrain torque margin.")

    elif goal.application == "quadruped":
        if project.rotary_joint is None:
            updates["rotary_joint"] = {
                "name": f"{project.project_name}_joint",
                "bearing": "608zz",
                "block_d_mm": 35.0,
                "arm_len_mm": 90.0,
            }
            decisions.append("Added rotary joint module for leg articulation.")
        if project.servo_mount is None:
            updates["servo_mount"] = {"name": f"{project.project_name}_hip_mount", "servo_type": "mg996r", "plate_w_mm": 100.0, "plate_h_mm": 60.0}
            decisions.append("Added servo mount module for actuation interface.")
        if project.gripper is None:
            updates["gripper"] = {"name": f"{project.project_name}_end_effector", "servo_type": "mg996r", "max_payload_n": 4.0, "lever_arm_mm": 35.0}
            decisions.append("Added gripper module as default end effector.")

    if not updates:
        return project, {"applied": False, "reason": "no missing modules for chosen goal"}

    merged = ProjectSpec.model_validate({**project.model_dump(), **updates})
    return merged, {"applied": True, "goal": goal.application, "decisions": decisions, "added_modules": sorted(list(updates.keys()))}
