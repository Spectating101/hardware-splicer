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
