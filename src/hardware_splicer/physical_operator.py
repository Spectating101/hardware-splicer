"""Generic physical-operator contract for Hardware Splicer.

This module lifts the fabrication boundary above 3D printers.  A physical
operator may be a printer, CNC/laser tool, programmer/debug probe, bench
instrument or robot.  The agent-facing side may observe and prepare work, but
anything that moves, heats, cuts, flashes, energises or otherwise actuates the
physical world is represented by a server-created execution plan whose digest
is what the human approves.

The module deliberately contains no network discovery, no raw shell/command
surface and no device credentials.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .fabrication_operator import FabricationValidationError

_OPERATOR_KINDS = frozenset({"printer", "cnc", "laser", "programmer", "instrument", "robot"})
_ACTION_CLASSES = frozenset({"observe", "prepare", "risk_reduce", "actuate"})
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value.strip()):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return value.strip()


def _jsonable(value: Any) -> Any:
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return json.loads(text)
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("physical operator payload must be canonical JSON") from exc


def canonical_payload_sha256(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        raise FabricationValidationError("physical operator payload must be an object")
    text = json.dumps(_jsonable(dict(payload)), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PhysicalActionDescriptor:
    name: str
    action_class: str
    description: str

    def __post_init__(self) -> None:
        _id(self.name, "action.name")
        if self.action_class not in _ACTION_CLASSES:
            raise FabricationValidationError("invalid physical action class")
        if not isinstance(self.description, str) or not self.description.strip():
            raise FabricationValidationError("action description is required")

    @property
    def requires_human_grant(self) -> bool:
        return self.action_class == "actuate"

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["requires_human_grant"] = self.requires_human_grant
        return value


@dataclass(frozen=True)
class PhysicalOperatorDescriptor:
    operator_id: str
    kind: str
    display_name: str
    capabilities: tuple[str, ...]
    actions: tuple[PhysicalActionDescriptor, ...]

    def __post_init__(self) -> None:
        _id(self.operator_id, "operator_id")
        if self.kind not in _OPERATOR_KINDS:
            raise FabricationValidationError("unsupported physical operator kind")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise FabricationValidationError("display_name is required")
        if not self.actions:
            raise FabricationValidationError("physical operator must declare actions")
        names = [action.name for action in self.actions]
        if len(names) != len(set(names)):
            raise FabricationValidationError("physical operator action names must be unique")
        for capability in self.capabilities:
            _id(capability, "capability")

    def action(self, name: str) -> PhysicalActionDescriptor:
        for action in self.actions:
            if action.name == name:
                return action
        raise FabricationValidationError(f"operator {self.operator_id!r} does not expose action {name!r}")

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema": "hardware_splicer.physical_operator_descriptor.v1",
            "operator_id": self.operator_id,
            "kind": self.kind,
            "display_name": self.display_name,
            "capabilities": list(self.capabilities),
            "actions": [action.public_dict() for action in self.actions],
        }


@dataclass(frozen=True)
class PhysicalExecutionPlan:
    schema: str
    project_id: str
    mission_id: str
    operator_id: str
    operator_kind: str
    action: str
    action_class: str
    payload: Mapping[str, Any]
    payload_sha256: str

    @classmethod
    def create(
        cls,
        *,
        descriptor: PhysicalOperatorDescriptor,
        project_id: str,
        mission_id: str,
        action: str,
        payload: Mapping[str, Any],
    ) -> "PhysicalExecutionPlan":
        action_desc = descriptor.action(action)
        normalized = _jsonable(dict(payload))
        return cls(
            schema="hardware_splicer.physical_execution_plan.v1",
            project_id=_id(project_id, "project_id"),
            mission_id=_id(mission_id, "mission_id"),
            operator_id=descriptor.operator_id,
            operator_kind=descriptor.kind,
            action=action_desc.name,
            action_class=action_desc.action_class,
            payload=normalized,
            payload_sha256=canonical_payload_sha256(normalized),
        )

    @property
    def requires_human_grant(self) -> bool:
        return self.action_class == "actuate"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["requires_human_grant"] = self.requires_human_grant
        return value


class PhysicalOperatorRegistry:
    """Server-owned catalogue of safe operator descriptors and private handles.

    Public listing never returns handles, endpoints or credentials.  A future
    MCP/API projection should expose :meth:`public_list` and plan creation, not
    arbitrary registration.
    """

    def __init__(self) -> None:
        self._entries: dict[str, tuple[PhysicalOperatorDescriptor, Any]] = {}

    def register(self, descriptor: PhysicalOperatorDescriptor, handle: Any) -> None:
        if descriptor.operator_id in self._entries:
            raise FabricationValidationError(f"duplicate physical operator {descriptor.operator_id!r}")
        self._entries[descriptor.operator_id] = (descriptor, handle)

    def descriptor(self, operator_id: str) -> PhysicalOperatorDescriptor:
        key = _id(operator_id, "operator_id")
        try:
            return self._entries[key][0]
        except KeyError as exc:
            raise FabricationValidationError(f"unknown physical operator {key!r}") from exc

    def private_handle(self, operator_id: str) -> Any:
        key = _id(operator_id, "operator_id")
        try:
            return self._entries[key][1]
        except KeyError as exc:
            raise FabricationValidationError(f"unknown physical operator {key!r}") from exc

    def public_list(self, *, kinds: Iterable[str] | None = None) -> list[dict[str, Any]]:
        allowed = set(kinds) if kinds is not None else None
        if allowed is not None and not allowed <= _OPERATOR_KINDS:
            raise FabricationValidationError("unknown physical operator kind filter")
        values = []
        for descriptor, _handle in self._entries.values():
            if allowed is None or descriptor.kind in allowed:
                values.append(descriptor.public_dict())
        return sorted(values, key=lambda item: item["operator_id"])

    def plan(
        self,
        *,
        operator_id: str,
        project_id: str,
        mission_id: str,
        action: str,
        payload: Mapping[str, Any],
    ) -> PhysicalExecutionPlan:
        return PhysicalExecutionPlan.create(
            descriptor=self.descriptor(operator_id),
            project_id=project_id,
            mission_id=mission_id,
            action=action,
            payload=payload,
        )


def printer_descriptor(*, operator_id: str, display_name: str) -> PhysicalOperatorDescriptor:
    return PhysicalOperatorDescriptor(
        operator_id=operator_id,
        kind="printer",
        display_name=display_name,
        capabilities=("additive_fabrication", "job_status"),
        actions=(
            PhysicalActionDescriptor("status", "observe", "Read printer/job state."),
            PhysicalActionDescriptor("stage", "prepare", "Stage an already verified fabrication artifact."),
            PhysicalActionDescriptor("start", "actuate", "Begin physical printing."),
            PhysicalActionDescriptor("pause", "risk_reduce", "Pause an active print."),
            PhysicalActionDescriptor("cancel", "risk_reduce", "Cancel an active print."),
            PhysicalActionDescriptor("resume", "actuate", "Resume physical printing."),
        ),
    )


def programmer_descriptor(*, operator_id: str, display_name: str) -> PhysicalOperatorDescriptor:
    return PhysicalOperatorDescriptor(
        operator_id=operator_id,
        kind="programmer",
        display_name=display_name,
        capabilities=("firmware_programming", "target_identity", "verify"),
        actions=(
            PhysicalActionDescriptor("inspect_target", "observe", "Read programmer/target identity without writing."),
            PhysicalActionDescriptor("stage_firmware", "prepare", "Bind firmware and target into a server execution plan."),
            PhysicalActionDescriptor("flash", "actuate", "Write the approved firmware artifact to the target."),
            PhysicalActionDescriptor("abort", "risk_reduce", "Abort an in-progress programming operation where supported."),
        ),
    )


def machine_tool_descriptor(*, operator_id: str, kind: str, display_name: str) -> PhysicalOperatorDescriptor:
    if kind not in {"cnc", "laser"}:
        raise FabricationValidationError("machine tool kind must be 'cnc' or 'laser'")
    return PhysicalOperatorDescriptor(
        operator_id=operator_id,
        kind=kind,
        display_name=display_name,
        capabilities=("subtractive_fabrication", "job_status", "preflight"),
        actions=(
            PhysicalActionDescriptor("status", "observe", "Read controller/job state."),
            PhysicalActionDescriptor("preflight", "prepare", "Validate a server-generated machine job without motion."),
            PhysicalActionDescriptor("stage", "prepare", "Stage a verified machine job."),
            PhysicalActionDescriptor("start", "actuate", "Begin cutting/engraving motion."),
            PhysicalActionDescriptor("pause", "risk_reduce", "Pause active motion where supported."),
            PhysicalActionDescriptor("cancel", "risk_reduce", "Stop and cancel the active job."),
            PhysicalActionDescriptor("resume", "actuate", "Resume active cutting/engraving motion."),
        ),
    )
