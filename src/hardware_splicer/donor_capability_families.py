"""Static salvage capability-family policy over canonical donor evidence.

Family definitions describe what a reusable capability *means* to the planner and
what investigation would be useful. They never own donor facts. Qualification is
derived from the donor projection produced by ``mission_donors.read_donors`` and
therefore cannot upgrade a model/document claim into physical truth.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Mapping, Sequence

from .fabrication_operator import FabricationValidationError

_GRADE_ORDER = {None: 0, "agent_assertion": 1, "re_observation": 2, "document": 3, "person_measurement": 4}
_ROLE_TOKEN = re.compile(r"[^a-z0-9]+")


def _request(
    request_id: str,
    kind: str,
    purpose: str,
    *,
    destructive: bool = False,
    energized: bool = False,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "kind": kind,
        "purpose": purpose,
        "destructive": destructive,
        "energized": energized,
        "requires_human_or_bounded_instrument": True,
    }


_FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "family_id": "salvage.passive_switch",
        "priority": 1,
        "label": "Passive switch / button / end-stop",
        "role_aliases": (
            "switch",
            "button",
            "momentary button",
            "momentary switch",
            "push button",
            "limit switch",
            "end stop",
            "endstop",
            "microswitch",
        ),
        "minimum_evidence": (
            "contact mapping",
            "open/closed state transition observed by continuity or equivalent bounded test",
        ),
        "optional_evidence": (
            "normally-open/normally-closed behavior",
            "contact resistance",
            "debounce behavior",
            "mounting geometry",
        ),
        "investigation_requests": (
            _request("continuity-open-closed", "continuity", "Observe contact continuity in both mechanical states."),
            _request("identify-common-contact", "continuity", "Map common/NO/NC contacts when more than two contacts exist."),
        ),
        "planner_interface": {
            "kind": "digital_input",
            "capability": "binary_human_or_mechanical_control",
            "requires_driver": False,
            "mechanical_output": False,
        },
        "adapters": {
            "firmware": "gpio input with explicit pull/debounce policy",
            "electrical": "pull-up/pull-down or level interface only when required by the chosen controller",
            "mechanical": "mounting bracket or actuator linkage as required by geometry",
        },
        "hazards": ("unknown external voltage on a switch harness",),
        "refusal_conditions": ("contact is still connected to an energized or unidentified power circuit",),
        "residual_unknowns": ("rated lifetime", "manufacturer current/voltage rating unless independently documented"),
    },
    {
        "family_id": "salvage.led_indicator",
        "priority": 2,
        "label": "LED / simple light indicator",
        "role_aliases": ("led", "indicator led", "status led", "lamp", "indicator lamp"),
        "minimum_evidence": (
            "terminal or contact mapping",
            "polarity when polarity-sensitive",
            "safe drive-voltage/current bounds or a verified existing series-limiting path",
            "visible output observed during a bounded test",
        ),
        "optional_evidence": ("forward voltage", "brightness at test current", "color", "mounting geometry"),
        "investigation_requests": (
            _request("led-diode-test", "electrical", "Use a bounded diode/low-current test to determine polarity and approximate forward behavior."),
            _request("indicator-observation", "observation", "Record visible output under the approved bounded test condition.", energized=True),
        ),
        "planner_interface": {
            "kind": "indicator_output",
            "capability": "visible_indicator",
            "requires_driver": "depends_on_verified_drive_bounds",
            "mechanical_output": False,
        },
        "adapters": {
            "firmware": "digital/PWM output when the verified electrical interface permits it",
            "electrical": "current limiting and transistor/driver stage when direct GPIO drive is not verified",
            "mechanical": "light-pipe or panel mount adapter as needed",
        },
        "hazards": ("unknown harness voltage", "missing current limiting"),
        "refusal_conditions": ("safe current/voltage bounds cannot be established for energized testing",),
        "residual_unknowns": ("absolute maximum rating", "long-term brightness/lifetime"),
    },
    {
        "family_id": "salvage.buzzer",
        "priority": 2,
        "label": "Simple buzzer / beeper",
        "role_aliases": ("buzzer", "beeper", "piezo buzzer", "active buzzer", "passive buzzer"),
        "minimum_evidence": (
            "terminal mapping",
            "safe drive bounds",
            "audible output observed during a bounded test",
        ),
        "optional_evidence": ("active/passive behavior", "resonant frequency", "current draw", "polarity"),
        "investigation_requests": (
            _request("buzzer-resistance", "electrical", "Measure non-energized terminal resistance/continuity before applying power."),
            _request("buzzer-bounded-tone", "observation", "Observe output at a bounded approved voltage or drive waveform.", energized=True),
        ),
        "planner_interface": {
            "kind": "indicator_output",
            "capability": "audible_indicator",
            "requires_driver": "depends_on_verified_drive_bounds",
            "mechanical_output": False,
        },
        "adapters": {
            "firmware": "digital output for active buzzer or timer/PWM tone generation for passive buzzer",
            "electrical": "transistor/driver stage when verified current exceeds controller limits",
            "mechanical": "acoustic opening/mount as needed",
        },
        "hazards": ("unknown drive voltage",),
        "refusal_conditions": ("energized test requested without established safe drive bounds",),
        "residual_unknowns": ("sound-pressure rating", "absolute maximum rating"),
    },
    {
        "family_id": "salvage.dc_motor",
        "priority": 3,
        "label": "Simple brushed DC motor / gearmotor",
        "role_aliases": ("dc motor", "brushed motor", "brushed dc motor", "gearmotor", "dc gearmotor", "gear motor"),
        "minimum_evidence": (
            "motor terminal mapping",
            "winding continuity/resistance",
            "bounded safe test-voltage or source-derived drive range",
            "rotation observed during a bounded test",
        ),
        "optional_evidence": (
            "no-load current",
            "stall/current-limit characterization",
            "direction versus polarity",
            "speed estimate",
            "shaft geometry",
            "mounting geometry",
        ),
        "investigation_requests": (
            _request("motor-terminal-resistance", "electrical", "Measure resistance/continuity across candidate motor terminals."),
            _request("motor-bounded-rotation", "observation", "Apply a current-limited bounded test and observe rotation.", energized=True),
            _request("motor-polarity-direction", "observation", "Observe rotation direction for a known polarity under the same bounded test.", energized=True),
            _request("motor-geometry", "dimensional", "Measure shaft and mounting geometry needed by the proposed mechanism."),
        ),
        "planner_interface": {
            "kind": "rotary_actuator",
            "capability": "bidirectional_rotation",
            "requires_driver": "h_bridge_or_equivalent_for_bidirectional_control",
            "mechanical_output": True,
        },
        "adapters": {
            "firmware": "direction/PWM control through the selected driver",
            "electrical": "H-bridge or bounded unidirectional switch sized from verified current evidence",
            "mechanical": "shaft coupler/gear/pulley and mount derived from measured geometry",
        },
        "hazards": ("stall current", "pinch/entanglement", "back-EMF", "unknown gearbox condition"),
        "refusal_conditions": (
            "direct GPIO drive",
            "unbounded energized spin test",
            "visible mechanical damage that makes rotation unsafe",
        ),
        "residual_unknowns": ("rated lifetime", "thermal limit", "rated torque unless independently characterized"),
    },
    {
        "family_id": "salvage.fan",
        "priority": 3,
        "label": "Low-voltage fan",
        "role_aliases": ("fan", "cooling fan", "dc fan", "brushless fan", "blower"),
        "minimum_evidence": (
            "power-contact mapping",
            "safe supply voltage/polarity",
            "rotation/airflow observed during a bounded test",
        ),
        "optional_evidence": ("current draw", "tach output", "PWM/control input", "airflow", "mounting geometry"),
        "investigation_requests": (
            _request("fan-contact-map", "electrical", "Map supply and any tach/PWM contacts without assuming wire colors."),
            _request("fan-bounded-spin", "observation", "Observe spin/airflow from a current-limited approved supply.", energized=True),
        ),
        "planner_interface": {
            "kind": "airflow_actuator",
            "capability": "forced_airflow",
            "requires_driver": "depends_on_verified_current_and_control_interface",
            "mechanical_output": True,
        },
        "adapters": {
            "firmware": "optional PWM/tach support only when the corresponding interface is verified",
            "electrical": "supply switch/driver when controller cannot safely source the verified load",
            "mechanical": "duct/grille/mount as required",
        },
        "hazards": ("rotating blades", "unknown wire mapping", "startup current"),
        "refusal_conditions": ("unprotected damaged blades", "energized test without established supply bounds"),
        "residual_unknowns": ("rated airflow", "bearing life", "tach/PWM semantics unless verified"),
    },
    {
        "family_id": "salvage.stepper_motor",
        "priority": 4,
        "label": "Stepper motor",
        "role_aliases": ("stepper", "stepper motor", "bipolar stepper", "unipolar stepper"),
        "minimum_evidence": (
            "coil grouping from resistance/continuity measurements",
            "safe phase-current/drive bound or trusted source evidence",
            "bounded step/rotation observation using a suitable driver",
        ),
        "optional_evidence": ("steps per revolution", "holding current", "shaft geometry", "mounting geometry"),
        "investigation_requests": (
            _request("stepper-pairwise-resistance", "electrical", "Measure pairwise resistance to identify coil groups before energizing."),
            _request("stepper-bounded-motion", "observation", "Use a current-limited stepper driver to observe controlled stepping.", energized=True),
            _request("stepper-geometry", "dimensional", "Measure shaft and mounting geometry for the intended mechanism."),
        ),
        "planner_interface": {
            "kind": "positioned_rotary_actuator",
            "capability": "open_loop_incremental_motion",
            "requires_driver": "stepper_driver",
            "mechanical_output": True,
        },
        "adapters": {
            "firmware": "step/direction or driver-specific sequencer",
            "electrical": "current-limited stepper driver sized from verified coil evidence",
            "mechanical": "coupler/pulley/lead-screw interface from measured geometry",
        },
        "hazards": ("coil overheating", "pinch/entanglement", "back-EMF", "unknown harness topology"),
        "refusal_conditions": ("direct GPIO drive", "energizing unidentified windings without current limiting"),
        "residual_unknowns": ("rated torque", "thermal duty cycle", "exact step angle unless measured/documented"),
    },
)


def list_capability_families() -> list[dict[str, Any]]:
    """Return a detached copy of the static family policy."""
    return [copy.deepcopy(value) for value in _FAMILIES]


def match_capability_family(role: str) -> dict[str, Any] | None:
    """Match a canonical donor functional role conservatively by normalized alias."""
    normalized = _normalize_role(role)
    for family in _FAMILIES:
        if normalized in family["role_aliases"]:
            return copy.deepcopy(family)
    return None


def project_family_capability(
    *,
    role: str,
    evidence_grade: str | None,
    contract_state: str,
    unresolved_facts: Sequence[str],
) -> dict[str, Any] | None:
    """Attach family policy without changing the underlying donor evidence state."""
    if evidence_grade not in _GRADE_ORDER:
        raise FabricationValidationError("capability family received an unsupported evidence grade")
    if contract_state not in {"unknown", "partial", "verified"}:
        raise FabricationValidationError("capability family received an unsupported contract state")
    if isinstance(unresolved_facts, (str, bytes, bytearray)) or not isinstance(unresolved_facts, Sequence):
        raise FabricationValidationError("capability family unresolved_facts must be a list")
    if any(not isinstance(value, str) for value in unresolved_facts):
        raise FabricationValidationError("capability family unresolved_facts must contain strings")
    family = match_capability_family(role)
    if family is None:
        return None
    unresolved = sorted(set(unresolved_facts))
    verified = contract_state == "verified" and evidence_grade == "person_measurement" and not unresolved
    architecture_usable = contract_state != "unknown"
    if verified:
        state = "verified"
    elif architecture_usable:
        state = "bounded_partial"
    else:
        state = "investigation_required"
    return {
        "family_id": family["family_id"],
        "label": family["label"],
        "priority": family["priority"],
        "role": role.strip(),
        "qualification": {
            "state": state,
            "evidence_grade": evidence_grade,
            "contract_state": contract_state,
            "architecture_usable": architecture_usable,
            "ready_for_execution": verified,
            "unresolved_facts": unresolved,
        },
        "minimum_evidence": list(family["minimum_evidence"]),
        "optional_evidence": list(family["optional_evidence"]),
        "recommended_investigation": [] if verified else copy.deepcopy(list(family["investigation_requests"])),
        "planner_interface": copy.deepcopy(family["planner_interface"]),
        "adapters": copy.deepcopy(family["adapters"]),
        "hazards": list(family["hazards"]),
        "refusal_conditions": list(family["refusal_conditions"]),
        "residual_unknowns_after_qualification": list(family["residual_unknowns"]),
        "truth_contract": {
            "family_policy_is_evidence": False,
            "role_match_establishes_physical_capability": False,
            "qualification_derived_from_canonical_donor_projection": True,
            "family_policy_may_promote_evidence": False,
        },
    }


def project_donor_families(donor: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project all recognized families from one mission donor projection."""
    if not isinstance(donor, Mapping):
        raise FabricationValidationError("donor family projection requires a donor object")
    capabilities = donor.get("capabilities") or []
    if not isinstance(capabilities, list):
        raise FabricationValidationError("donor capabilities must be a list")
    state = donor.get("contract_state")
    unresolved = donor.get("missing_facts") or []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in capabilities:
        if not isinstance(row, Mapping):
            raise FabricationValidationError("donor capability must be an object")
        role = row.get("role")
        if not isinstance(role, str) or not role.strip():
            raise FabricationValidationError("donor capability role must be nonempty text")
        projected = project_family_capability(
            role=role,
            evidence_grade=row.get("grade"),
            contract_state=state,
            unresolved_facts=unresolved,
        )
        if projected is None or projected["family_id"] in seen:
            continue
        seen.add(projected["family_id"])
        result.append(projected)
    return sorted(result, key=lambda row: (int(row["priority"]), str(row["family_id"])))


def _normalize_role(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise FabricationValidationError("capability family role must be bounded text")
    return " ".join(part for part in _ROLE_TOKEN.sub(" ", value.strip().lower()).split() if part)
