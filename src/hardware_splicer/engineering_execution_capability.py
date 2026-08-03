"""Runtime capability truth for bounded engineering execution adapters."""

from __future__ import annotations

import shutil
import sys
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field

from .engineering_execution import (
    ExecutionOperation,
    default_execution_root,
    execution_enabled,
)


EXECUTION_CAPABILITY_SCHEMA = "hardware_splicer.engineering_execution_capability.v1"


class CapabilityBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ExecutionToolCapability(CapabilityBase):
    operation: ExecutionOperation
    adapter_available: bool = True
    tool: str | None = None
    tool_path: str | None = None
    tool_installed: bool = False
    executable_under_host_policy: bool = False
    preview_available: bool = True
    physical_operation: bool = False
    limitations: list[str] = Field(default_factory=list)


class EngineeringExecutionCapability(CapabilityBase):
    schema_version: str = EXECUTION_CAPABILITY_SCHEMA
    execution_root: str
    execution_enabled: bool
    operations: list[ExecutionToolCapability] = Field(default_factory=list)
    prohibited_operations: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


_TOOL_BY_OPERATION = {
    ExecutionOperation.ARTIFACT_HASH: None,
    ExecutionOperation.PYTHON_COMPILE: sys.executable,
    ExecutionOperation.PYTEST: sys.executable,
    ExecutionOperation.KICAD_ERC: "kicad-cli",
    ExecutionOperation.KICAD_DRC: "kicad-cli",
    ExecutionOperation.NGSPICE: "ngspice",
    ExecutionOperation.PLATFORMIO_BUILD: "pio",
    ExecutionOperation.COLCON_BUILD: "colcon",
    ExecutionOperation.COLCON_TEST: "colcon",
    ExecutionOperation.ROS2_DOCTOR: "ros2",
    ExecutionOperation.URDF_CHECK: "check_urdf",
}


def _tool_path(tool: str | None) -> str | None:
    if tool is None:
        return "internal:sha256"
    if tool == sys.executable:
        return sys.executable
    return shutil.which(tool)


def build_engineering_execution_capability() -> EngineeringExecutionCapability:
    """Report actual host tool availability without probing hardware or the network."""

    enabled = execution_enabled()
    operations: list[ExecutionToolCapability] = []
    for operation in ExecutionOperation:
        tool = _TOOL_BY_OPERATION[operation]
        path = _tool_path(tool)
        installed = bool(path)
        limitations = [
            "No network access is authorized by Hardware Splicer, but OS-level network isolation is not enforced by this adapter.",
            "No device access, firmware flashing, power control, actuator command, or motion operation is supported.",
        ]
        if not enabled:
            limitations.append("Execution is disabled by host policy; preview remains available.")
        if not installed:
            limitations.append(f"Required tool is not installed for {operation.value}.")
        operations.append(
            ExecutionToolCapability(
                operation=operation,
                tool=tool or "internal-sha256",
                tool_path=path,
                tool_installed=installed,
                executable_under_host_policy=enabled and installed,
                preview_available=True,
                physical_operation=False,
                limitations=limitations,
            )
        )
    return EngineeringExecutionCapability(
        execution_root=str(default_execution_root()),
        execution_enabled=enabled,
        operations=operations,
        prohibited_operations=[
            "arbitrary_shell",
            "network_fetch",
            "device_access",
            "firmware_flash",
            "power_control",
            "actuator_command",
            "robot_motion",
            "field_release",
        ],
        metadata={
            "adapter_count": len(operations),
            "installed_tool_count": len([row for row in operations if row.tool_installed]),
            "executable_operation_count": len([row for row in operations if row.executable_under_host_policy]),
            "preview_only_when_disabled": True,
            "shell": False,
            "network_authorized": False,
            "network_isolation_enforced": False,
            "device_access_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    )
