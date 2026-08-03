"""Compile preview-only execution checks from an engineering plan."""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .engineering_execution import ExecutionOperation, ExecutionRequest
from .engineering_source_graph import EngineeringSourceGraph


ENGINEERING_EXECUTION_PLAN_SCHEMA = "hardware_splicer.engineering_execution_plan.v1"


class ExecutionPlanBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EngineeringExecutionPlan(ExecutionPlanBase):
    schema_version: str = ENGINEERING_EXECUTION_PLAN_SCHEMA
    project_id: str = Field(min_length=1)
    checks: list[ExecutionRequest] = Field(default_factory=list)
    unresolved: list[Dict[str, Any]] = Field(default_factory=list)
    prohibited_operations: list[str] = Field(
        default_factory=lambda: [
            "firmware_flash",
            "device_programming",
            "power_control",
            "actuator_command",
            "robot_motion",
            "field_release",
        ]
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        result: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("id", str(key))
                result.append(row)
            elif isinstance(item, list):
                result.extend(dict(row) for row in item if isinstance(row, Mapping))
        return result
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _slug(value: Any, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip("-._").lower()
    return token[:100] or fallback


def _local_path(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or "://" in text or text.startswith("package://"):
        return None
    return text


def _request(
    checks: list[ExecutionRequest],
    *,
    execution_id: str,
    operation: ExecutionOperation,
    workspace: str = ".",
    target: str | None = None,
    options: Mapping[str, Any] | None = None,
    expected_outputs: list[str] | None = None,
    timeout_s: int = 60,
) -> None:
    key = (operation.value, workspace, target, tuple(sorted((options or {}).items())))
    existing = {
        (row.operation.value, row.workspace, row.target, tuple(sorted(row.options.items())))
        for row in checks
    }
    if key in existing:
        return
    checks.append(
        ExecutionRequest(
            execution_id=execution_id,
            operation=operation,
            workspace=workspace,
            target=target,
            options=dict(options or {}),
            expected_outputs=list(expected_outputs or []),
            timeout_s=timeout_s,
            execute=False,
        )
    )


def build_engineering_execution_plan(
    plan: Mapping[str, Any],
    *,
    source_graph: EngineeringSourceGraph | Mapping[str, Any] | None = None,
) -> EngineeringExecutionPlan:
    """Create non-executing checks from source and artifact identities."""

    machine = _mapping(plan.get("machine_project"))
    project_id = str(machine.get("project_id") or plan.get("project_name") or "engineering-project")
    graph = source_graph if isinstance(source_graph, EngineeringSourceGraph) else EngineeringSourceGraph.model_validate(source_graph or plan.get("engineering_source_graph") or {})
    checks: list[ExecutionRequest] = []
    unresolved: list[Dict[str, Any]] = []

    source_types = {row.source_type.value for row in graph.sources}
    has_repository = bool(source_types & {"repository", "firmware"})
    if has_repository:
        _request(
            checks,
            execution_id="exec-python-compile",
            operation=ExecutionOperation.PYTHON_COMPILE,
            target="src",
            timeout_s=120,
        )
        _request(
            checks,
            execution_id="exec-pytest",
            operation=ExecutionOperation.PYTEST,
            options={"targets": ["tests"]},
            timeout_s=300,
        )

    for source in graph.sources:
        metadata = source.metadata if isinstance(source.metadata, Mapping) else {}
        artifact_kind = str(metadata.get("artifact_kind") or "").lower()
        path = _local_path(source.uri)
        if artifact_kind == "urdf":
            if path:
                _request(
                    checks,
                    execution_id=f"exec-urdf-{_slug(source.source_id, 'model')}",
                    operation=ExecutionOperation.URDF_CHECK,
                    target=path,
                )
            else:
                unresolved.append(
                    {
                        "source_id": source.source_id,
                        "operation": "urdf_check",
                        "reason": "URDF source is not available as a local workspace path.",
                    }
                )
        if artifact_kind == "firmware_manifest":
            manifest = metadata.get("firmware_manifest") if isinstance(metadata.get("firmware_manifest"), Mapping) else {}
            workspace = _local_path(manifest.get("workspace") or manifest.get("project_dir") or source.uri) or "."
            toolchain = str(manifest.get("toolchain") or "").lower()
            if "platformio" in toolchain or manifest.get("board_profile"):
                _request(
                    checks,
                    execution_id=f"exec-firmware-build-{_slug(source.source_id, 'firmware')}",
                    operation=ExecutionOperation.PLATFORMIO_BUILD,
                    workspace=workspace,
                    timeout_s=300,
                )
            else:
                unresolved.append(
                    {
                        "source_id": source.source_id,
                        "operation": "firmware_build",
                        "reason": "Firmware manifest has no supported bounded build adapter.",
                    }
                )
        if artifact_kind == "ros_interface_manifest":
            manifest = metadata.get("ros_interface_manifest") if isinstance(metadata.get("ros_interface_manifest"), Mapping) else {}
            workspace = _local_path(manifest.get("workspace") or source.uri) or "."
            _request(
                checks,
                execution_id=f"exec-colcon-build-{_slug(source.source_id, 'ros')}",
                operation=ExecutionOperation.COLCON_BUILD,
                workspace=workspace,
                timeout_s=600,
            )
            _request(
                checks,
                execution_id=f"exec-colcon-test-{_slug(source.source_id, 'ros')}",
                operation=ExecutionOperation.COLCON_TEST,
                workspace=workspace,
                timeout_s=600,
            )
            _request(
                checks,
                execution_id=f"exec-ros-doctor-{_slug(source.source_id, 'ros')}",
                operation=ExecutionOperation.ROS2_DOCTOR,
                workspace=workspace,
                timeout_s=120,
            )

    normalized = _mapping(plan.get("normalized_intake"))
    fabrication = []
    for key in ("fabrication_artifacts", "manufacturing_artifacts", "release_artifacts"):
        fabrication.extend(_rows(normalized.get(key)))
        fabrication.extend(_rows(plan.get(key)))
    for index, row in enumerate(fabrication):
        raw_id = row.get("artifact_id") or row.get("id") or row.get("name") or f"artifact-{index + 1}"
        kind = str(row.get("kind") or row.get("format") or "").lower()
        path = _local_path(row.get("path") or row.get("ref") or row.get("uri"))
        if not path:
            unresolved.append(
                {
                    "artifact_id": str(raw_id),
                    "operation": "artifact_hash",
                    "reason": "Release artifact is not available as a local workspace path.",
                }
            )
            continue
        _request(
            checks,
            execution_id=f"exec-hash-{_slug(raw_id, f'artifact-{index + 1}')}",
            operation=ExecutionOperation.ARTIFACT_HASH,
            target=path,
        )
        if kind in {"kicad_schematic", "schematic", "kicad_sch"} or path.endswith(".kicad_sch"):
            _request(
                checks,
                execution_id=f"exec-erc-{_slug(raw_id, 'schematic')}",
                operation=ExecutionOperation.KICAD_ERC,
                target=path,
                timeout_s=180,
            )
        if kind in {"kicad_pcb", "pcb"} or path.endswith(".kicad_pcb"):
            _request(
                checks,
                execution_id=f"exec-drc-{_slug(raw_id, 'pcb')}",
                operation=ExecutionOperation.KICAD_DRC,
                target=path,
                timeout_s=180,
            )
        if kind in {"spice", "spice_netlist", "netlist"} or path.endswith((".cir", ".sp", ".spice")):
            _request(
                checks,
                execution_id=f"exec-spice-{_slug(raw_id, 'netlist')}",
                operation=ExecutionOperation.NGSPICE,
                target=path,
                timeout_s=120,
            )

    return EngineeringExecutionPlan(
        project_id=project_id,
        checks=checks,
        unresolved=unresolved,
        metadata={
            "preview_only": True,
            "check_count": len(checks),
            "unresolved_count": len(unresolved),
            "automatic_execution": False,
            "network_authorized": False,
            "device_access_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    )
