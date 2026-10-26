"""Protocol-neutral manufacturing fleet: enroll, verify, route; never silently operate.

Device discovery is restricted to locally enrolled endpoints. The model neither
scans a network nor chooses arbitrary URLs, credentials or physical commands.
No print-start, temperature, motion or raw toolpath operation exists here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .octoprint import ManufacturingRefusal


STATES = frozenset({"idle", "printing", "paused", "error", "offline", "unknown"})


@dataclass(frozen=True)
class MachineCapabilities:
    machine_type: str
    file_formats: tuple[str, ...]
    can_read_status: bool
    can_monitor_job: bool
    can_stage_file: bool
    can_start_job: bool = False
    can_control_motion: bool = False
    can_control_heaters: bool = False
    build_volume_mm: tuple[float, float, float] | None = None

    def __post_init__(self):
        if self.machine_type not in ("fdm", "resin", "cnc", "laser", "pcb", "robot"):
            raise ValueError("Unsupported machine type; do not guess capabilities")
        if not self.file_formats or any(
            not isinstance(fmt, str) or not fmt.startswith(".") for fmt in self.file_formats
        ):
            raise ValueError("Machine requires explicit artifact formats")
        if self.build_volume_mm is not None and (
            len(self.build_volume_mm) != 3 or any(v <= 0 for v in self.build_volume_mm)
        ):
            raise ValueError("Invalid device build dimensions")


@dataclass(frozen=True)
class MachineObservation:
    machine_id: str
    controller: str
    state: str
    capabilities: MachineCapabilities
    controller_protocol_verified: bool
    detail: str = ""

    def __post_init__(self):
        if self.state not in STATES:
            raise ValueError("Invalid machine state")
        if not self.machine_id or not self.controller:
            raise ValueError("Machine identity and driver are required")


class MachineDriver(Protocol):
    def inspect(self, machine_id: str) -> MachineObservation:
        """Confirm the controller's actual protocol and read current state."""


@dataclass(frozen=True)
class ManufacturingRequest:
    machine_type: str
    artifact_suffix: str
    need_monitoring: bool = True
    need_staging: bool = False

    def __post_init__(self):
        if not self.artifact_suffix.startswith("."):
            raise ValueError("Artifact suffix must be explicit")


@dataclass(frozen=True)
class ManufacturingPlan:
    machine_id: str
    controller: str
    artifact_suffix: str
    status: str
    requires_operator_approval: bool = True
    start_authorized: bool = False
    automated_fabrication_authorized: bool = False


class ManufacturingFleet:
    """Operator-enrolled machines with conservative capability-based planning.

    Enroll one local machine driver per operator-approved ID. No DNS/mDNS, LAN
    scanning, guessing by manufacturer, or background machine interactions.
    """
    def __init__(self):
        self._drivers: dict[str, MachineDriver] = {}

    def enroll(self, machine_id: str, driver: MachineDriver) -> None:
        if not isinstance(machine_id, str) or not machine_id.strip() or machine_id in self._drivers:
            raise ManufacturingRefusal("Machine ID missing or already enrolled")
        self._drivers[machine_id] = driver

    def inspect(self, machine_id: str) -> MachineObservation:
        driver = self._drivers.get(machine_id)
        if driver is None:
            raise ManufacturingRefusal("Machine is not locally enrolled")
        observation = driver.inspect(machine_id)
        if observation.machine_id != machine_id or not observation.controller_protocol_verified:
            raise ManufacturingRefusal("Enrolled controller protocol could not be verified")
        return observation

    def inspect_all(self) -> list[MachineObservation]:
        return [self.inspect(machine_id) for machine_id in sorted(self._drivers)]

    def plan(self, request: ManufacturingRequest, *, machine_id: str | None = None) -> ManufacturingPlan:
        ids = [machine_id] if machine_id else sorted(self._drivers)
        matches = []
        for device_id in ids:
            observed = self.inspect(device_id)
            caps = observed.capabilities
            if (observed.state == "idle"
                and caps.machine_type == request.machine_type
                and request.artifact_suffix in caps.file_formats
                and caps.can_read_status
                and (not request.need_monitoring or caps.can_monitor_job)
                and (not request.need_staging or caps.can_stage_file)):
                matches.append(observed)
        if not matches:
            raise ManufacturingRefusal("No verified, idle and compatible enrolled machine")
        if len(matches) > 1:
            raise ManufacturingRefusal("Multiple compatible devices; operator must select one")
        selected = matches[0]
        return ManufacturingPlan(
            machine_id=selected.machine_id,
            controller=selected.controller,
            artifact_suffix=request.artifact_suffix,
            status="candidate_only",
        )


class OctoPrintDriver:
    """Adapts the existing OctoPrint client without manufacturing privilege."""
    def __init__(self, client):
        self.client = client

    def inspect(self, machine_id: str) -> MachineObservation:
        version = self.client._http.get("/api/version")
        version.raise_for_status()
        metadata = version.json()
        if not isinstance(metadata, dict) or not str(metadata.get("text", "")).startswith("OctoPrint"):
            raise ManufacturingRefusal("Not an authenticated OctoPrint controller")
        status = self.client.printer_status()
        flags = status["state"].get("flags", {})
        if not isinstance(flags, dict):
            raise ManufacturingRefusal("Missing printer state flags")
        if flags.get("printing"):
            state = "printing"
        elif flags.get("paused"):
            state = "paused"
        elif flags.get("error") or flags.get("closedOrError"):
            state = "error"
        elif flags.get("operational"):
            state = "idle"
        else:
            state = "offline"
        return MachineObservation(
            machine_id=machine_id, controller="octoprint", state=state,
            controller_protocol_verified=True,
            capabilities=MachineCapabilities(
                machine_type="fdm", file_formats=(".gcode", ".gco"),
                can_read_status=True, can_monitor_job=True,
                can_stage_file=bool(self.client._upload_allowed),
            ),
        )
