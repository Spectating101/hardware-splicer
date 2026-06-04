from __future__ import annotations

from typing import Any, Dict, List

from ..spec import ProjectSpec


def evaluate_safety_checks(project: ProjectSpec) -> List[Dict[str, Any]]:
    """
    Rule-based safety and integration flags for engineering review.
    """
    checks: List[Dict[str, Any]] = []

    motion_present = any([project.linear_axis, project.leadscrew_axis, project.pan_tilt, project.gripper, project.rotary_joint, project.belt_reduction])
    if motion_present:
        checks.append({"severity": "info", "topic": "motion", "message": "Motion subsystem present: add e-stop and startup interlock in controller firmware."})

    if project.system_goal is not None and project.system_goal.environment == "outdoor":
        checks.append({"severity": "warn", "topic": "environment", "message": "Outdoor profile: validate ingress sealing, connector strain relief, and corrosion plan."})

    if project.enclosure is None and project.electronics is not None:
        checks.append({"severity": "warn", "topic": "electronics", "message": "Electronics anchor provided without explicit enclosure; confirm touch-safe and cable-safe mounting."})

    if project.linear_axis is not None and project.linear_axis.payload_n > 20.0:
        checks.append({"severity": "warn", "topic": "loads", "message": "High payload force on linear axis: verify frame stiffness and pinch-zone guarding."})

    if not checks:
        checks.append({"severity": "info", "topic": "general", "message": "No rule-based safety flags raised."})

    return checks
