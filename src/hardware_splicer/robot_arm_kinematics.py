"""URDF projection and independent PyBullet kinematics checks for typed robot-arm proposals.

This layer deliberately does not turn proposal geometry into physical truth. It emits a
kinematics-only URDF with proxy collision geometry, then asks an external robotics engine
(PyBullet) to load the model and check forward/inverse kinematics plus proxy self-collision.

Authority remains closed. Link masses, inertia, stiffness, actual CAD collision meshes,
transmission behavior, electrical limits, calibration, and bench evidence are outside this
oracle and must remain unresolved.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence
from xml.etree import ElementTree as ET

from .robot_arm_design import RobotArmDesignProposal


SCHEMA_VERSION = "hardware_splicer.robot_arm_kinematics.v1"
_PROXY_LINK_WIDTH_M = 0.03
_PROXY_LINK_HEIGHT_M = 0.03


@dataclass(frozen=True)
class RobotArmUrdfArtifact:
    text: str
    joint_count: int
    chain_length_m: float
    tool_link_name: str = "tool0"
    collision_geometry_authority: str = "proxy_only"
    physical_authority: str = "none"


def _fmt(value: float) -> str:
    return f"{float(value):.9g}"


def _vec(values: Sequence[float]) -> str:
    return " ".join(_fmt(float(row)) for row in values)


def _add_proxy_link(robot: ET.Element, name: str, length_m: float, *, base: bool = False) -> None:
    link = ET.SubElement(robot, "link", {"name": name})
    visual = ET.SubElement(link, "visual")
    collision = ET.SubElement(link, "collision")
    if base:
        size = (0.06, 0.06, 0.04)
        ET.SubElement(visual, "origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
        ET.SubElement(collision, "origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
    else:
        size = (max(length_m, 0.001), _PROXY_LINK_WIDTH_M, _PROXY_LINK_HEIGHT_M)
        origin = f"{_fmt(length_m / 2.0)} 0 0"
        ET.SubElement(visual, "origin", {"xyz": origin, "rpy": "0 0 0"})
        ET.SubElement(collision, "origin", {"xyz": origin, "rpy": "0 0 0"})
    ET.SubElement(ET.SubElement(visual, "geometry"), "box", {"size": _vec(size)})
    ET.SubElement(ET.SubElement(collision, "geometry"), "box", {"size": _vec(size)})


def generate_robot_arm_urdf(proposal: RobotArmDesignProposal, *, robot_name: str = "hs_arm_candidate") -> RobotArmUrdfArtifact:
    """Project a typed proposal to a serial URDF without inventing physical ratings.

    Joint effort/velocity fields are zero-valued schema placeholders required by URDF and
    must not be interpreted as actuator limits. Collision boxes are geometry proxies only.
    The proposal link length is interpreted as the distance from its joint to the next joint.
    """

    robot = ET.Element("robot", {"name": robot_name})
    _add_proxy_link(robot, "base_link", 0.0, base=True)

    previous_link = "base_link"
    previous_length_m = 0.0
    chain_length_m = 0.0

    for index, row in enumerate(proposal.joints):
        length_m = float(row.link_length_mm) / 1000.0
        child_link = f"{row.joint_id}_link"
        _add_proxy_link(robot, child_link, length_m)

        joint = ET.SubElement(robot, "joint", {"name": row.joint_id, "type": row.joint_type})
        ET.SubElement(joint, "parent", {"link": previous_link})
        ET.SubElement(joint, "child", {"link": child_link})
        origin_x = 0.0 if index == 0 else previous_length_m
        ET.SubElement(joint, "origin", {"xyz": f"{_fmt(origin_x)} 0 0", "rpy": "0 0 0"})
        ET.SubElement(joint, "axis", {"xyz": _vec(row.axis)})
        if row.joint_type == "revolute":
            lower = math.radians(float(row.lower_limit_deg if row.lower_limit_deg is not None else -180.0))
            upper = math.radians(float(row.upper_limit_deg if row.upper_limit_deg is not None else 180.0))
            ET.SubElement(
                joint,
                "limit",
                {
                    "lower": _fmt(lower),
                    "upper": _fmt(upper),
                    "effort": "0",
                    "velocity": "0",
                },
            )
        previous_link = child_link
        previous_length_m = length_m
        chain_length_m += length_m

    ET.SubElement(robot, "link", {"name": "tool0"})
    tool_joint = ET.SubElement(robot, "joint", {"name": "tool0_fixed", "type": "fixed"})
    ET.SubElement(tool_joint, "parent", {"link": previous_link})
    ET.SubElement(tool_joint, "child", {"link": "tool0"})
    ET.SubElement(tool_joint, "origin", {"xyz": f"{_fmt(previous_length_m)} 0 0", "rpy": "0 0 0"})

    xml_text = ET.tostring(robot, encoding="unicode")
    return RobotArmUrdfArtifact(
        text=xml_text,
        joint_count=len(proposal.joints),
        chain_length_m=chain_length_m,
    )


def _position_error_mm(a: Sequence[float], b: Sequence[float]) -> float:
    return 1000.0 * math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def run_pybullet_kinematics_oracle(
    proposal: RobotArmDesignProposal,
    *,
    urdf_path: str,
    workspace_samples: int = 256,
    collision_samples: int = 128,
    random_seed: int = 11,
) -> Dict[str, Any]:
    """Run an external FK/IK/workspace/proxy-collision probe against a generated URDF."""

    try:
        import pybullet as p
    except Exception as exc:  # pragma: no cover - exercised in dedicated CI
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "provider_unavailable",
            "error": str(exc),
            "authority_effect": "none",
            "motion_authorized": False,
        }

    artifact = generate_robot_arm_urdf(proposal)
    client = p.connect(p.DIRECT)
    try:
        flags = int(getattr(p, "URDF_USE_SELF_COLLISION", 0)) | int(
            getattr(p, "URDF_USE_SELF_COLLISION_EXCLUDE_PARENT", 0)
        )
        body = p.loadURDF(str(urdf_path), useFixedBase=True, flags=flags, physicsClientId=client)
        joint_count = p.getNumJoints(body, physicsClientId=client)
        movable: list[int] = []
        lower: list[float] = []
        upper: list[float] = []
        tool_index: int | None = None
        parent_by_link: dict[int, int] = {}
        joint_names: list[str] = []

        for index in range(joint_count):
            info = p.getJointInfo(body, index, physicsClientId=client)
            joint_type = int(info[2])
            link_name = info[12].decode("utf-8")
            parent_index = int(info[16])
            parent_by_link[index] = parent_index
            if link_name == artifact.tool_link_name:
                tool_index = index
            if joint_type != p.JOINT_FIXED:
                movable.append(index)
                joint_names.append(info[1].decode("utf-8"))
                lower.append(float(info[8]))
                upper.append(float(info[9]))

        if tool_index is None:
            raise RuntimeError("generated URDF loaded without tool0 link")

        for index in movable:
            p.resetJointState(body, index, 0.0, physicsClientId=client)
        p.performCollisionDetection(physicsClientId=client)
        zero_state = p.getLinkState(body, tool_index, computeForwardKinematics=True, physicsClientId=client)
        zero_position = tuple(float(row) for row in zero_state[4])
        expected_zero = (artifact.chain_length_m, 0.0, 0.0)
        zero_error_mm = _position_error_mm(zero_position, expected_zero)

        chain = artifact.chain_length_m
        target = (0.65 * chain, 0.20 * chain, 0.15 * chain)
        ranges = [max(u - l, 1e-6) for l, u in zip(lower, upper)]
        rest = [0.0] * len(movable)
        ik_solution = p.calculateInverseKinematics(
            body,
            tool_index,
            target,
            lowerLimits=lower,
            upperLimits=upper,
            jointRanges=ranges,
            restPoses=rest,
            maxNumIterations=300,
            residualThreshold=1e-7,
            physicsClientId=client,
        )
        for index, value in zip(movable, ik_solution):
            p.resetJointState(body, index, float(value), physicsClientId=client)
        ik_state = p.getLinkState(body, tool_index, computeForwardKinematics=True, physicsClientId=client)
        ik_position = tuple(float(row) for row in ik_state[4])
        ik_error_mm = _position_error_mm(ik_position, target)
        ik_limit_compliant = all(
            l - 1e-6 <= float(value) <= u + 1e-6
            for value, l, u in zip(ik_solution, lower, upper)
        )

        unreachable_target = (1.25 * chain, 0.0, 0.0)
        unreachable_solution = p.calculateInverseKinematics(
            body,
            tool_index,
            unreachable_target,
            lowerLimits=lower,
            upperLimits=upper,
            jointRanges=ranges,
            restPoses=rest,
            maxNumIterations=300,
            residualThreshold=1e-7,
            physicsClientId=client,
        )
        for index, value in zip(movable, unreachable_solution):
            p.resetJointState(body, index, float(value), physicsClientId=client)
        unreachable_state = p.getLinkState(body, tool_index, computeForwardKinematics=True, physicsClientId=client)
        unreachable_position = tuple(float(row) for row in unreachable_state[4])
        unreachable_error_mm = _position_error_mm(unreachable_position, unreachable_target)

        rng = random.Random(random_seed)
        workspace_positions: list[tuple[float, float, float]] = []
        proxy_collision_free = 0
        proxy_collision_states = 0
        nonadjacent_contact_pairs: set[tuple[int, int]] = set()
        sample_total = max(workspace_samples, collision_samples)
        for sample_index in range(sample_total):
            state_values = [rng.uniform(l, u) for l, u in zip(lower, upper)]
            for index, value in zip(movable, state_values):
                p.resetJointState(body, index, value, physicsClientId=client)
            if sample_index < workspace_samples:
                state = p.getLinkState(body, tool_index, computeForwardKinematics=True, physicsClientId=client)
                workspace_positions.append(tuple(float(row) for row in state[4]))
            if sample_index < collision_samples:
                p.performCollisionDetection(physicsClientId=client)
                contacts = p.getContactPoints(bodyA=body, bodyB=body, physicsClientId=client)
                invalid_pairs: set[tuple[int, int]] = set()
                for contact in contacts:
                    a, b = int(contact[3]), int(contact[4])
                    if a == b:
                        continue
                    pair = tuple(sorted((a, b)))
                    adjacent = parent_by_link.get(a) == b or parent_by_link.get(b) == a
                    if adjacent:
                        continue
                    invalid_pairs.add(pair)
                proxy_collision_states += 1
                if not invalid_pairs:
                    proxy_collision_free += 1
                nonadjacent_contact_pairs.update(invalid_pairs)

        radii = [math.sqrt(x * x + y * y + z * z) for x, y, z in workspace_positions]
        max_radius = max(radii) if radii else 0.0
        min_radius = min(radii) if radii else 0.0
        collision_free_fraction = (
            proxy_collision_free / proxy_collision_states if proxy_collision_states else 0.0
        )

        return {
            "schema_version": SCHEMA_VERSION,
            "status": "pass",
            "engine": "pybullet",
            "urdf_load_pass": True,
            "proposal_joint_count": len(proposal.joints),
            "loaded_movable_joint_count": len(movable),
            "movable_joint_names": joint_names,
            "chain_length_m": round(chain, 6),
            "zero_pose_tool_position_m": [round(row, 6) for row in zero_position],
            "zero_pose_chain_error_mm": round(zero_error_mm, 6),
            "ik_target_position_m": [round(row, 6) for row in target],
            "ik_solved_position_m": [round(row, 6) for row in ik_position],
            "ik_position_error_mm": round(ik_error_mm, 6),
            "ik_within_5mm": ik_error_mm <= 5.0,
            "ik_joint_limits_respected": bool(ik_limit_compliant),
            "unreachable_target_position_m": [round(row, 6) for row in unreachable_target],
            "unreachable_solution_position_m": [round(row, 6) for row in unreachable_position],
            "unreachable_target_error_mm": round(unreachable_error_mm, 6),
            "unreachable_target_not_falsely_closed": unreachable_error_mm >= 20.0,
            "workspace_sample_count": len(workspace_positions),
            "workspace_min_radius_m": round(min_radius, 6),
            "workspace_max_radius_m": round(max_radius, 6),
            "workspace_max_to_chain_ratio": round(max_radius / chain, 6) if chain else 0.0,
            "proxy_collision_sample_count": proxy_collision_states,
            "proxy_collision_free_count": proxy_collision_free,
            "proxy_collision_free_fraction": round(collision_free_fraction, 6),
            "proxy_nonadjacent_contact_pairs": [list(row) for row in sorted(nonadjacent_contact_pairs)],
            "collision_geometry_authority": artifact.collision_geometry_authority,
            "physical_authority": "none",
            "authority_effect": "none",
            "motion_authorized": False,
            "limitations": [
                "Generated collision geometry is a simple box proxy, not CAD-derived physical geometry.",
                "URDF effort/velocity values are zero-valued schema placeholders and are not actuator ratings.",
                "No link mass, inertia, stiffness, drivetrain, electrical, thermal, calibration, or bench evidence is closed here.",
                "IK success proves only that the proxy kinematic model can reach the target within configured joint limits.",
            ],
        }
    finally:
        p.disconnect(physicsClientId=client)
