"""Typed robot-arm design proposals and conservative deterministic evaluation.

This module is a specialized engineering surface for the model-first path. The model may
propose a kinematic chain and reference only visible actuator identities. Hardware Splicer
then checks identity, reach, and a conservative payload-only torque bound without claiming
that the arm is physically safe or motion-ready.

The important epistemic split is intentional:
- model: proposes architecture and design dimensions;
- deterministic code: validates references and computes bounded checks;
- missing link mass, collision, calibration, feedback, or bench evidence stays unresolved;
- no result here grants fabrication, power, motion, operation, or release authority.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Callable, Dict, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .machine_project import AuthorityState
from .robot_topology import (
    CoordinateFrame,
    JointType,
    RobotActuator,
    RobotJoint,
    RobotLink,
    RobotTopology,
    RobotGenre,
)


SCHEMA_VERSION = "hardware_splicer.robot_arm_design.v1"
EVALUATION_SCHEMA = "hardware_splicer.robot_arm_design_evaluation.v1"
_G = 9.80665


class RobotArmDesignError(ValueError):
    """Raised when a robot-arm proposal violates the bounded design contract."""


class ArmDesignModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ArmJointProposal(ArmDesignModel):
    joint_id: str = Field(min_length=1, max_length=96)
    joint_type: str = "revolute"
    axis: list[float] = Field(min_length=3, max_length=3)
    link_length_mm: float = Field(gt=0.0, le=2_000.0)
    actuator_part_id: str | None = None
    lower_limit_deg: float | None = None
    upper_limit_deg: float | None = None

    @field_validator("joint_type")
    @classmethod
    def bounded_joint_type(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in {"revolute", "prismatic"}:
            raise ValueError("robot-arm joints must be revolute or prismatic")
        return normalized

    @field_validator("axis")
    @classmethod
    def nonzero_axis(cls, value: list[float]) -> list[float]:
        rendered = [float(row) for row in value]
        norm = math.sqrt(sum(row * row for row in rendered))
        if norm <= 1e-9:
            raise ValueError("joint axis must be nonzero")
        return [round(row / norm, 9) for row in rendered]

    @model_validator(mode="after")
    def ordered_limits(self) -> "ArmJointProposal":
        if self.lower_limit_deg is not None and self.upper_limit_deg is not None:
            if self.lower_limit_deg >= self.upper_limit_deg:
                raise ValueError("joint lower limit must be below upper limit")
        return self


class RobotArmDesignProposal(ArmDesignModel):
    schema_version: str = SCHEMA_VERSION
    status: str = "model_proposed"
    reasoning: str = Field(default="", max_length=8_000)
    joints: list[ArmJointProposal] = Field(min_length=1, max_length=8)
    end_effector: str = Field(default="unresolved", min_length=1, max_length=128)
    source_ids: list[str] = Field(default_factory=list, max_length=32)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=32)
    authority_effect: str = "none"
    automatic_execution: bool = False

    @field_validator("authority_effect")
    @classmethod
    def zero_authority(cls, value: str) -> str:
        if value != "none":
            raise ValueError("robot-arm proposal cannot change engineering authority")
        return value

    @field_validator("automatic_execution")
    @classmethod
    def no_auto_execution(cls, value: bool) -> bool:
        if value:
            raise ValueError("robot-arm proposal cannot execute automatically")
        return False

    @model_validator(mode="after")
    def unique_joint_ids(self) -> "RobotArmDesignProposal":
        ids = [row.joint_id for row in self.joints]
        if len(ids) != len(set(ids)):
            raise ValueError("robot-arm joint IDs must be unique")
        return self


class ArmEvaluationFinding(ArmDesignModel):
    code: str
    status: str
    message: str
    joint_id: str | None = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    blocking: bool = False


class RobotArmDesignEvaluation(ArmDesignModel):
    schema_version: str = EVALUATION_SCHEMA
    status: str
    findings: list[ArmEvaluationFinding]
    topology: Dict[str, Any]
    summary: Dict[str, Any]
    authority_effect: str = "none"
    automatic_execution: bool = False
    fabrication_authorized: bool = False
    power_on_authorized: bool = False
    motion_authorized: bool = False
    release_authorized: bool = False


def _extract_json_object(text: str) -> Dict[str, Any]:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    parsed = json.loads(value)
    if not isinstance(parsed, Mapping):
        raise RobotArmDesignError("robot-arm response must be one JSON object")
    return dict(parsed)


def _inventory_rows(inventory: Sequence[Mapping[str, Any]] | None) -> list[Dict[str, Any]]:
    return [dict(row) for row in list(inventory or []) if isinstance(row, Mapping)]


def _part_id(row: Mapping[str, Any]) -> str:
    return str(row.get("component_id") or row.get("module_id") or row.get("part_id") or "").strip()


def _inventory_index(inventory: Sequence[Mapping[str, Any]] | None) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for row in _inventory_rows(inventory):
        identity = _part_id(row)
        if identity:
            result[identity] = row
    return result


def parse_robot_arm_design(
    value: Mapping[str, Any] | str,
    *,
    inventory: Sequence[Mapping[str, Any]] | None = None,
    known_source_ids: Sequence[str] | None = None,
) -> RobotArmDesignProposal:
    body = _extract_json_object(value) if isinstance(value, str) else dict(value)
    body.setdefault("schema_version", SCHEMA_VERSION)
    body.setdefault("status", "model_proposed")
    body.setdefault("authority_effect", "none")
    body.setdefault("automatic_execution", False)
    try:
        proposal = RobotArmDesignProposal.model_validate(body)
    except ValidationError as exc:
        raise RobotArmDesignError(str(exc)) from exc

    inventory_ids = set(_inventory_index(inventory))
    invented_parts = sorted(
        {
            str(row.actuator_part_id)
            for row in proposal.joints
            if row.actuator_part_id and str(row.actuator_part_id) not in inventory_ids
        }
    )
    if invented_parts:
        raise RobotArmDesignError(
            "robot-arm proposal referenced actuator identities absent from visible inventory: "
            + ", ".join(invented_parts)
        )

    known = {str(row) for row in list(known_source_ids or []) if str(row)}
    invented_sources = sorted(set(proposal.source_ids) - known) if known else []
    if invented_sources:
        raise RobotArmDesignError(
            "robot-arm proposal referenced source identities absent from visible evidence: "
            + ", ".join(invented_sources)
        )
    return proposal


def robot_arm_design_prompt(
    goal: str,
    *,
    requirements: Mapping[str, Any],
    inventory: Sequence[Mapping[str, Any]] | None = None,
    source_ids: Sequence[str] | None = None,
) -> str:
    visible_inventory = []
    for row in _inventory_rows(inventory)[:32]:
        visible_inventory.append(
            {
                "component_id": _part_id(row),
                "type": row.get("type") or row.get("category"),
                "continuous_torque_nm": row.get("continuous_torque_nm"),
                "voltage_v": row.get("voltage_v") or row.get("nominal_voltage_v"),
                "feedback": row.get("feedback"),
            }
        )
    return f"""Propose one typed robot-arm design candidate from only the supplied project-visible facts.

Goal:
{str(goal).strip()}

Requirements:
{json.dumps(dict(requirements), indent=2, sort_keys=True)}

Visible candidate inventory:
{json.dumps(visible_inventory, indent=2, sort_keys=True)}

Visible evidence source IDs:
{json.dumps([str(row) for row in list(source_ids or [])])}

Return JSON only with exactly these top-level fields:
{{
  "reasoning": "brief design rationale",
  "joints": [
    {{
      "joint_id": "stable proposed joint name",
      "joint_type": "revolute or prismatic",
      "axis": [0, 0, 1],
      "link_length_mm": 100,
      "actuator_part_id": "one visible component_id or null",
      "lower_limit_deg": null,
      "upper_limit_deg": null
    }}
  ],
  "end_effector": "proposed end-effector class or unresolved",
  "source_ids": [],
  "unresolved_questions": [],
  "authority_effect": "none",
  "automatic_execution": false
}}

Rules:
- Do not invent actuator IDs, ratings, evidence IDs, measurements, or physical proof.
- Joint count, axes, and link lengths are proposals, not verified truth.
- Reference only actuator component_id values visible above; use null when not defensible.
- Keep unresolved requirements explicit rather than filling them with common hobby-arm defaults.
- Do not assume Arduino, ESP32, SG90, MG996R, or any other familiar part unless that exact identity is visible.
- Do not claim fabrication, power, motion, operation, or release authority.
"""


def propose_robot_arm_design(
    goal: str,
    *,
    requirements: Mapping[str, Any],
    inventory: Sequence[Mapping[str, Any]] | None = None,
    source_ids: Sequence[str] | None = None,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> RobotArmDesignProposal:
    prompt = robot_arm_design_prompt(
        goal,
        requirements=requirements,
        inventory=inventory,
        source_ids=source_ids,
    )
    if llm_callable is None:
        from .integrations.llm_text_client import call_llm_chat

        response = call_llm_chat(
            prompt,
            stage="planning",
            temperature=0.0,
            json_mode=True,
            timeout_s=120,
            system=(
                "You are a proposal-only robot-arm design engineer. Return one typed design "
                "candidate grounded only in supplied requirements and inventory."
            ),
        )
    else:
        response = llm_callable(
            prompt,
            stage="planning",
            temperature=0.0,
            json_mode=True,
            timeout_s=120,
            system=(
                "You are a proposal-only robot-arm design engineer. Return one typed design "
                "candidate grounded only in supplied requirements and inventory."
            ),
        )
    if not isinstance(response, Mapping) or not response.get("ok"):
        raise RobotArmDesignError(
            str((response or {}).get("error") if isinstance(response, Mapping) else "robot-arm provider failed")
        )
    return parse_robot_arm_design(
        str(response.get("content") or "{}"),
        inventory=inventory,
        known_source_ids=source_ids,
    )


def build_robot_arm_topology_from_proposal(
    proposal: RobotArmDesignProposal,
) -> RobotTopology:
    """Project a typed arm proposal into canonical topology without canned joint semantics."""

    topology_id = "robot-arm-proposal"
    frames: list[CoordinateFrame] = [
        CoordinateFrame(
            frame_id="base-frame",
            attached_object_id="base-link",
            authority=AuthorityState.PROPOSED,
        )
    ]
    links: list[RobotLink] = [
        RobotLink(
            link_id="base-link",
            name="base link",
            frame_id="base-frame",
            authority=AuthorityState.PROPOSED,
        )
    ]
    joints: list[RobotJoint] = []
    actuators: list[RobotActuator] = []
    unresolved: list[Dict[str, Any]] = []
    parent_link = "base-link"
    parent_frame = "base-frame"

    for index, joint in enumerate(proposal.joints):
        child_link = f"{joint.joint_id}-link"
        child_frame = f"{joint.joint_id}-frame"
        frames.append(
            CoordinateFrame(
                frame_id=child_frame,
                parent_frame_id=parent_frame,
                attached_object_id=child_link,
                authority=AuthorityState.PROPOSED,
                metadata={"proposed_link_length_mm": joint.link_length_mm},
            )
        )
        links.append(
            RobotLink(
                link_id=child_link,
                name=child_link.replace("-", " "),
                parent_link_id=parent_link,
                frame_id=child_frame,
                authority=AuthorityState.PROPOSED,
                metadata={"proposed_link_length_mm": joint.link_length_mm},
            )
        )
        actuator_id = f"actuator-{joint.joint_id}"
        limits: Dict[str, Any] = {}
        if joint.lower_limit_deg is not None:
            limits["lower_deg"] = joint.lower_limit_deg
        if joint.upper_limit_deg is not None:
            limits["upper_deg"] = joint.upper_limit_deg
        if joint.lower_limit_deg is None or joint.upper_limit_deg is None:
            unresolved.append(
                {
                    "object_id": joint.joint_id,
                    "field": "limits",
                    "reason": "Joint workspace limits remain proposal-incomplete.",
                }
            )
        joints.append(
            RobotJoint(
                joint_id=joint.joint_id,
                name=joint.joint_id.replace("-", " "),
                joint_type=JointType(joint.joint_type),
                parent_link_id=parent_link,
                child_link_id=child_link,
                axis=joint.axis,
                limits=limits,
                actuator_id=actuator_id,
                firmware_joint_id=joint.joint_id.replace("-", "_"),
                middleware_joint_name=joint.joint_id,
                calibration_ref=f"calibration/{joint.joint_id}",
                authority=AuthorityState.PROPOSED,
                metadata={"proposal_index": index},
            )
        )
        actuators.append(
            RobotActuator(
                actuator_id=actuator_id,
                name=actuator_id.replace("-", " "),
                actuator_type="proposed_joint_actuator",
                joint_ids=[joint.joint_id],
                source_part_id=joint.actuator_part_id,
                firmware_channel_id=f"fw-{joint.joint_id}",
                command_interface=f"command/{joint.joint_id}",
                feedback_interface=f"state/{joint.joint_id}",
                authority=AuthorityState.PROPOSED,
                metadata={"source_part_declared": bool(joint.actuator_part_id)},
            )
        )
        if not joint.actuator_part_id:
            unresolved.append(
                {
                    "object_id": actuator_id,
                    "field": "source_part_id",
                    "reason": "No visible actuator identity is bound to this proposed joint.",
                }
            )
        parent_link = child_link
        parent_frame = child_frame

    unresolved.extend(
        [
            {
                "object_id": topology_id,
                "field": "link_mass_and_inertia",
                "reason": "Link mass/inertia evidence is required for full gravity and dynamic torque closure.",
            },
            {
                "object_id": topology_id,
                "field": "collision_geometry",
                "reason": "Collision geometry and self-collision checks are not yet present.",
            },
            {
                "object_id": topology_id,
                "field": "calibration_and_repeatability",
                "reason": "Calibration/feedback evidence is required before repeatability or motion claims.",
            },
        ]
    )

    return RobotTopology(
        topology_id=topology_id,
        robot_genre=RobotGenre.SERIAL_MANIPULATOR,
        root_link_id="base-link",
        frames=frames,
        links=links,
        joints=joints,
        actuators=actuators,
        sensors=[],
        unresolved=unresolved,
        metadata={
            "source": "typed_robot_arm_model_proposal",
            "candidate_only": True,
            "motion_authorized": False,
            "automatic_execution": False,
        },
    )


def _number(source: Mapping[str, Any], key: str) -> float | None:
    value = source.get(key)
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_robot_arm_design(
    proposal: RobotArmDesignProposal,
    *,
    requirements: Mapping[str, Any],
    inventory: Sequence[Mapping[str, Any]] | None = None,
) -> RobotArmDesignEvaluation:
    """Evaluate reach and conservative payload-only torque without claiming motion readiness."""

    inventory_by_id = _inventory_index(inventory)
    findings: list[ArmEvaluationFinding] = []
    topology = build_robot_arm_topology_from_proposal(proposal)

    required_reach_mm = _number(requirements, "required_reach_mm")
    proposed_reach_mm = sum(row.link_length_mm for row in proposal.joints)
    if required_reach_mm is None:
        findings.append(
            ArmEvaluationFinding(
                code="REACH_REQUIREMENT_MISSING",
                status="unknown",
                message="No required reach is declared; geometric reach cannot close a requirement.",
                outputs={"proposed_chain_length_mm": round(proposed_reach_mm, 3)},
                blocking=True,
            )
        )
    else:
        reach_margin = proposed_reach_mm - required_reach_mm
        findings.append(
            ArmEvaluationFinding(
                code="GEOMETRIC_REACH_UPPER_BOUND",
                status="pass" if reach_margin >= 0 else "fail",
                message=(
                    "Proposed serial link-length sum meets the required reach upper bound."
                    if reach_margin >= 0
                    else "Proposed serial link-length sum is shorter than the required reach."
                ),
                inputs={"required_reach_mm": required_reach_mm},
                outputs={
                    "proposed_chain_length_mm": round(proposed_reach_mm, 3),
                    "reach_margin_mm": round(reach_margin, 3),
                },
                blocking=reach_margin < 0,
            )
        )
        findings.append(
            ArmEvaluationFinding(
                code="WORKSPACE_NOT_VERIFIED",
                status="review",
                message=(
                    "Link-length sum is only a geometric upper bound; actual reachable workspace "
                    "still depends on joint limits, axes, collisions, and mounting geometry."
                ),
                blocking=True,
            )
        )

    payload_mass_kg = _number(requirements, "payload_mass_kg")
    safety_factor = _number(requirements, "minimum_static_torque_safety_factor")
    if payload_mass_kg is None or safety_factor is None:
        missing = []
        if payload_mass_kg is None:
            missing.append("payload_mass_kg")
        if safety_factor is None:
            missing.append("minimum_static_torque_safety_factor")
        findings.append(
            ArmEvaluationFinding(
                code="TORQUE_REQUIREMENT_INCOMPLETE",
                status="unknown",
                message="Payload-only static torque acceptance cannot be bounded from requirements.",
                inputs={"missing": missing},
                blocking=True,
            )
        )
    else:
        remaining_mm = proposed_reach_mm
        for joint in proposal.joints:
            if joint.joint_type != "revolute":
                findings.append(
                    ArmEvaluationFinding(
                        code="PRISMATIC_LOAD_MODEL_UNSUPPORTED",
                        status="unknown",
                        message="This first arm evaluator does not yet calculate prismatic actuator force.",
                        joint_id=joint.joint_id,
                        blocking=True,
                    )
                )
                remaining_mm -= joint.link_length_mm
                continue
            required_payload_only = payload_mass_kg * _G * (remaining_mm / 1000.0) * safety_factor
            actuator = inventory_by_id.get(str(joint.actuator_part_id or ""), {})
            available_torque = _number(actuator, "continuous_torque_nm")
            if not joint.actuator_part_id:
                findings.append(
                    ArmEvaluationFinding(
                        code="ACTUATOR_IDENTITY_UNRESOLVED",
                        status="unknown",
                        message="No exact visible actuator identity is bound to the joint.",
                        joint_id=joint.joint_id,
                        outputs={"payload_only_required_torque_nm": round(required_payload_only, 4)},
                        blocking=True,
                    )
                )
            elif available_torque is None:
                findings.append(
                    ArmEvaluationFinding(
                        code="ACTUATOR_TORQUE_RATING_UNRESOLVED",
                        status="unknown",
                        message="Bound actuator has no visible continuous-torque rating.",
                        joint_id=joint.joint_id,
                        inputs={"actuator_part_id": joint.actuator_part_id},
                        outputs={"payload_only_required_torque_nm": round(required_payload_only, 4)},
                        blocking=True,
                    )
                )
            else:
                margin = available_torque - required_payload_only
                findings.append(
                    ArmEvaluationFinding(
                        code="PAYLOAD_ONLY_TORQUE_BOUND",
                        status="pass" if margin >= 0 else "fail",
                        message=(
                            "Actuator clears the conservative payload-only static torque bound."
                            if margin >= 0
                            else "Actuator fails the payload-only static torque bound."
                        ),
                        joint_id=joint.joint_id,
                        inputs={
                            "actuator_part_id": joint.actuator_part_id,
                            "continuous_torque_nm": available_torque,
                            "payload_mass_kg": payload_mass_kg,
                            "minimum_static_torque_safety_factor": safety_factor,
                            "remaining_chain_length_mm": remaining_mm,
                        },
                        outputs={
                            "payload_only_required_torque_nm": round(required_payload_only, 4),
                            "payload_only_torque_margin_nm": round(margin, 4),
                        },
                        blocking=margin < 0,
                    )
                )
            remaining_mm -= joint.link_length_mm

        findings.append(
            ArmEvaluationFinding(
                code="LINK_SELF_WEIGHT_TORQUE_UNRESOLVED",
                status="review",
                message=(
                    "Payload-only torque is not full joint sizing. Link self-weight, end-effector "
                    "mass, acceleration, friction, transmission loss, backlash, and shock remain unresolved."
                ),
                blocking=True,
            )
        )

    max_joint_count = _number(requirements, "max_joint_count")
    if max_joint_count is not None and len(proposal.joints) > int(max_joint_count):
        findings.append(
            ArmEvaluationFinding(
                code="JOINT_COUNT_LIMIT_EXCEEDED",
                status="fail",
                message="Proposed joint count exceeds the declared project limit.",
                inputs={"max_joint_count": int(max_joint_count)},
                outputs={"proposed_joint_count": len(proposal.joints)},
                blocking=True,
            )
        )

    if any(row.lower_limit_deg is None or row.upper_limit_deg is None for row in proposal.joints):
        findings.append(
            ArmEvaluationFinding(
                code="JOINT_LIMITS_INCOMPLETE",
                status="review",
                message="One or more joint limits are unresolved, so workspace cannot be closed.",
                blocking=True,
            )
        )

    findings.append(
        ArmEvaluationFinding(
            code="PHYSICAL_VALIDATION_REQUIRED",
            status="review",
            message=(
                "Collision, structural stiffness, transmission behavior, calibration, repeatability, "
                "wiring, current/thermal limits, and bench evidence remain required before motion."
            ),
            blocking=True,
        )
    )

    hard_failures = [row for row in findings if row.status == "fail"]
    blockers = [row for row in findings if row.blocking]
    status = "failed" if hard_failures else ("blocked" if blockers else "candidate")
    return RobotArmDesignEvaluation(
        status=status,
        findings=findings,
        topology=topology.model_dump(mode="json"),
        summary={
            "joint_count": len(proposal.joints),
            "proposed_chain_length_mm": round(proposed_reach_mm, 3),
            "finding_count": len(findings),
            "hard_failure_count": len(hard_failures),
            "blocking_count": len(blockers),
            "full_kinematics_verified": False,
            "full_dynamics_verified": False,
            "collision_verified": False,
            "physical_validation_required": True,
        },
        authority_effect="none",
        automatic_execution=False,
        fabrication_authorized=False,
        power_on_authorized=False,
        motion_authorized=False,
        release_authorized=False,
    )
