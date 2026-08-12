"""Bounded circuit-synthesis planning layer.

This package represents circuit intent, topology operators, constraints, and candidate
plans before handing work to the existing Hardware-Splicer compile/check spine.
``plan_circuit`` uses typed semantic planner selection on model-first paths and retains
the historical keyword dispatcher only for explicit offline compatibility/regression.
"""

from .ir import (
    CONSTRAINT_TYPES,
    CircuitIntent,
    Constraint,
    FunctionalPart,
    Port,
    SynthesisCandidate,
    TopologyOperator,
)

# Architecture ambiguity is a legitimate fail-closed planning constraint. It carries no
# physical authority and records that the model/operator must choose among multiple
# declared topology families rather than letting deterministic code guess one.
CONSTRAINT_TYPES.add("architecture")

from .analog_conditioning_planner import plan_analog_conditioning
from .battery_power_planner import plan_battery_power
from .candidate_bridge import compile_synthesis_candidate
from .h_bridge_planner import plan_h_bridge
from .level_shift_planner import plan_level_shift
from .motor_driver_planner import plan_motor_driver
from .operator_lowering import apply_operator_lowering
from .power_rail_planner import plan_power_rail
from .planner import plan_circuit
from .relay_switch_planner import plan_relay_switch
from .semantic_planner_selector import (
    PLANNER_REGISTRY,
    SemanticPlannerSelection,
    SemanticPlannerSelectionError,
    SemanticPlannerTrace,
    parse_semantic_planner_selection,
    plan_circuit_from_semantic_selection,
    planner_registry_payload,
    select_semantic_circuit_planner,
    semantic_plan_circuit,
    semantic_planner_prompt,
)
from .sensor_interface_planner import plan_sensor_interface
from .topology_library import (
    evaluate_topology_authority,
    primitive_for_operator,
    topology_library_card,
)

__all__ = [
    "CircuitIntent",
    "Constraint",
    "FunctionalPart",
    "Port",
    "SynthesisCandidate",
    "TopologyOperator",
    "compile_synthesis_candidate",
    "apply_operator_lowering",
    "plan_analog_conditioning",
    "plan_battery_power",
    "plan_circuit",
    "plan_h_bridge",
    "plan_level_shift",
    "plan_motor_driver",
    "plan_power_rail",
    "plan_relay_switch",
    "plan_sensor_interface",
    "PLANNER_REGISTRY",
    "SemanticPlannerSelection",
    "SemanticPlannerSelectionError",
    "SemanticPlannerTrace",
    "parse_semantic_planner_selection",
    "plan_circuit_from_semantic_selection",
    "planner_registry_payload",
    "select_semantic_circuit_planner",
    "semantic_plan_circuit",
    "semantic_planner_prompt",
    "evaluate_topology_authority",
    "primitive_for_operator",
    "topology_library_card",
]
