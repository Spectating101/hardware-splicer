"""Programmatic hardware engineering API."""

from ._exports import resolve_export as _resolve_export
from . import salvage_bringup

# Python normally binds an imported child module to the parent. Cache this
# lightweight child first so later SDK imports cannot shadow the public function.
del salvage_bringup

_MODULES = {
    "HardwareCompileResult": "schemas",
    "HardwareCompileSpec": "schemas",
    "CircuitIntent": "circuit_synthesis",
    "Constraint": "circuit_synthesis",
    "FunctionalPart": "circuit_synthesis",
    "Port": "circuit_synthesis",
    "SynthesisCandidate": "circuit_synthesis",
    "TopologyOperator": "circuit_synthesis",
    "apply_operator_lowering": "circuit_synthesis",
    "build_engineering_assurance": "engineering_assurance",
    "build_independent_review_packet": "engineering_assurance",
    "changed_assurance_dependencies": "engineering_assurance",
    "evaluate_assurance_delta": "engineering_assurance",
    "evaluate_topology_authority": "circuit_synthesis",
    "topology_library_card": "circuit_synthesis",
    "build_mechatronics_authority": "mechatronics_authority",
    "build_mechanical_authority": "mechanical_authority",
    "build_project_authority_packet": "scenario_runner",
    "build_authority_upgrade_plan": "project_intake",
    "build_evidence_capture_kit": "project_intake",
    "build_evidence_extraction_report": "evidence_extractor",
    "build_production_release_metrics": "production_release_metrics",
    "build_robotics_actuation_packet": "robotics_actuation",
    "build_robotics_platform_authority": "robotics_platform_authority",
    "build_robotics_simulation_packet": "robotics_simulation",
    "compile_scratch_build": "scratch_pipeline",
    "circuit_synthesis_capability": "sdk",
    "compose_design": "sdk",
    "dump_json": "sdk",
    "engine_doctor": "sdk",
    "list_catalog_builds": "sdk",
    "plan_analog_conditioning": "circuit_synthesis",
    "plan_battery_power": "circuit_synthesis",
    "plan_motor_driver": "circuit_synthesis",
    "plan_h_bridge": "circuit_synthesis",
    "plan_level_shift": "circuit_synthesis",
    "plan_power_rail": "circuit_synthesis",
    "plan_relay_switch": "circuit_synthesis",
    "plan_sensor_interface": "circuit_synthesis",
    "plan_circuit": "circuit_synthesis",
    "compile_synthesis_candidate": "circuit_synthesis",
    "plan_analog_conditioning_circuit": "sdk",
    "plan_battery_power_circuit": "sdk",
    "plan_circuit_synthesis": "sdk",
    "plan_h_bridge_circuit": "sdk",
    "plan_level_shift_circuit": "sdk",
    "plan_motor_driver_circuit": "sdk",
    "plan_power_rail_circuit": "sdk",
    "plan_salvage": "sdk",
    "plan_relay_switch_circuit": "sdk",
    "plan_sensor_interface_circuit": "sdk",
    "prove_module_ids": "scratch_pipeline",
    "resolve_inventory_parts": "sdk",
    "salvage_bringup": "sdk",
    "sdk_info": "sdk",
    "suggest_modules": "sdk",
    "synthesize_circuit": "sdk",
    "verify_engine": "sdk",
    "build_vision_evidence_report": "vision_evidence_assistant",
    "build_design_quality_gate": "design_quality",
    "CATALOG_BUILD_IDS": "build_compiler",
    "build_intake_salvage_package": "salvage_bridge",
    "compile_catalog_build": "build_compiler",
    "compile_hardware_bundle": "compiler",
    "resolve_build_id": "build_compiler",
    "resolve_parts_to_modules": "module_resolver",
    "enrich_intake_with_extracted_evidence": "evidence_extractor",
    "enrich_intake_with_vision_assistance": "vision_evidence_assistant",
    "load_project_intake": "project_intake",
    "load_hardware_scenario": "scenario_runner",
    "plan_project_from_intake": "project_intake",
    "run_project_intake": "project_intake",
    "run_hardware_scenario": "scenario_runner",
    "scenario_to_compile_spec": "scenario_runner",
}
__all__ = list(_MODULES)


def __getattr__(name):
    return _resolve_export(globals(), _MODULES, name)


def __dir__():
    return sorted(set(globals()).union(__all__, _MODULES.values()))
