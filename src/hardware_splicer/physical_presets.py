"""Safe descriptor presets for non-printer physical operators.

These presets describe authority classes only.  They do not contain drivers,
network locations, raw machine commands or credentials.  Real private handles
must be supplied by server configuration after the descriptor contract is
validated.
"""

from __future__ import annotations

from .physical_operator import PhysicalActionDescriptor, PhysicalOperatorDescriptor


def bench_instrument_descriptor(*, operator_id: str, display_name: str) -> PhysicalOperatorDescriptor:
    """Programmable bench instrument with explicit output authority.

    Passive reads are observations.  Configuration that does not energise the
    DUT is preparation.  Enabling/sourcing an output is actuation and therefore
    requires a human grant bound to the exact plan; disabling output is
    risk-reducing.
    """

    return PhysicalOperatorDescriptor(
        operator_id=operator_id,
        kind="instrument",
        display_name=display_name,
        capabilities=("measurement", "configured_output", "status"),
        actions=(
            PhysicalActionDescriptor("status", "observe", "Read instrument state."),
            PhysicalActionDescriptor("read", "observe", "Read an already configured measurement channel."),
            PhysicalActionDescriptor("configure", "prepare", "Prepare bounded server-side measurement/output settings without enabling output."),
            PhysicalActionDescriptor("enable_output", "actuate", "Enable the exact approved instrument output plan."),
            PhysicalActionDescriptor("disable_output", "risk_reduce", "Disable instrument output."),
        ),
    )


def camera_observer_descriptor(*, operator_id: str, display_name: str) -> PhysicalOperatorDescriptor:
    """Observation-only camera whose captures are retained as raw evidence inputs.

    Capturing an image is read-only with respect to the workpiece.  The resulting
    frame remains UNPROVEN and requires an explicit evidence-promotion step before
    it can establish or clear an engineering finding.
    """

    return PhysicalOperatorDescriptor(
        operator_id=operator_id,
        kind="instrument",
        display_name=display_name,
        capabilities=("vision_observation", "image_capture", "status"),
        actions=(
            PhysicalActionDescriptor("status", "observe", "Read configured camera availability."),
            PhysicalActionDescriptor("capture", "observe", "Capture and retain one immutable image observation."),
        ),
    )


def serial_observer_descriptor(*, operator_id: str, display_name: str) -> PhysicalOperatorDescriptor:
    """Read-only serial/console observer; no target writes are exposed."""

    return PhysicalOperatorDescriptor(
        operator_id=operator_id,
        kind="instrument",
        display_name=display_name,
        capabilities=("serial_observation", "boot_log_capture", "status"),
        actions=(
            PhysicalActionDescriptor("status", "observe", "Read configured serial observer availability."),
            PhysicalActionDescriptor("capture_log", "observe", "Capture and retain an immutable read-only serial transcript."),
        ),
    )


def robot_descriptor(*, operator_id: str, display_name: str) -> PhysicalOperatorDescriptor:
    """Robot/workcell authority surface around immutable motion-plan artifacts."""

    return PhysicalOperatorDescriptor(
        operator_id=operator_id,
        kind="robot",
        display_name=display_name,
        capabilities=("motion_execution", "workcell_status", "motion_preflight"),
        actions=(
            PhysicalActionDescriptor("status", "observe", "Read robot/workcell state."),
            PhysicalActionDescriptor("preflight_motion", "prepare", "Validate a server-generated motion plan without motion."),
            PhysicalActionDescriptor("execute_motion", "actuate", "Execute an approved immutable motion-plan artifact."),
            PhysicalActionDescriptor("stop", "risk_reduce", "Stop active robot motion."),
            PhysicalActionDescriptor("resume_motion", "actuate", "Resume the approved motion-plan artifact."),
        ),
    )
