"""High-level orchestration for deterministic design validation.

This keeps all entrypoints (CLI, API, future Blender/AR bridges) consistent:
- Compile high-level design -> `CircuitNetlist`
- Solve operating point + validate power tree
- Add spec-level checks (logic level mismatch, actuator external power)

Return values are JSON-friendly, but the core issues are still `SimulationIssue`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from src.engines.circuit_physics import SimulationIssue
from src.engines.design_compiler import compile_design, spec_level_issues
from src.engines.netlist_io import netlist_to_dict
from src.engines.power_tree_validator import validate_pcb_power_tree


@dataclass(frozen=True)
class ValidationOutput:
    compiled: Dict[str, Any]
    results: Dict[str, Any]
    issues: List[SimulationIssue]


def validate_high_level_design(design: Dict[str, Any]) -> ValidationOutput:
    compiled = compile_design(design)
    results, power_issues = validate_pcb_power_tree(compiled.netlist, constraints=compiled.constraints)

    # Convert spec-level dict issues to SimulationIssue for consistency.
    extra_issues: List[SimulationIssue] = []
    for item in spec_level_issues(design):
        extra_issues.append(
            SimulationIssue(
                severity=item.get("severity", "warning"),
                component=item.get("component", "unknown"),
                issue=item.get("issue", "issue"),
                explanation=item.get("explanation", ""),
                physics_data=item.get("physics_data", {}) or {},
                solution=item.get("solution", ""),
            )
        )

    all_issues = list(power_issues) + extra_issues

    compiled_payload = {
        "rails": compiled.rails,
        "netlist": netlist_to_dict(compiled.netlist),
        "constraints": {
            "source_limits": [sl.__dict__ for sl in compiled.constraints.source_limits],
            "max_trace_drop_v": compiled.constraints.max_trace_drop_v,
        },
    }

    results_payload = {
        "converged": results["converged"],
        "iterations": results["iterations"],
        "node_v": results["solution"].node_v,
        "vsource_i": results["solution"].vsource_i,
    }

    return ValidationOutput(compiled=compiled_payload, results=results_payload, issues=all_issues)


def validation_output_to_dict(out: ValidationOutput) -> Dict[str, Any]:
    return {
        "compiled": out.compiled,
        "results": out.results,
        "issues": [i.__dict__ for i in out.issues],
    }
