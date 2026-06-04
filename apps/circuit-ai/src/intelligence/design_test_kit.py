"""Backend design test kit for DIY/splice hardware plans.

This layer turns an engineering plan into an executable test contract. It is
deliberately split into two levels:
- abstract/module tests that can run from a DIY hardware plan
- deterministic DC power-tree tests when a structured netlist is supplied
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.engines.netlist_io import netlist_from_dict
from src.engines.power_tree_validator import PowerTreeConstraints, SourceCurrentLimit, validate_pcb_power_tree
from src.intelligence.diy_project_engineer import build_diy_project_engineering_plan
from src.intelligence.topology_evidence import enrich_payload_with_topology_evidence
from src.intelligence.topology_netlist_compiler import compile_topology_to_netlist


SCHEMA_VERSION = "hardware_design_test_kit.v1"

PASS = "pass"
WARNING = "warning"
FAIL = "fail"
BLOCKED = "blocked"
PENDING = "pending"

STATUS_WEIGHT = {
    PASS: 1.0,
    WARNING: 0.68,
    PENDING: 0.38,
    FAIL: 0.0,
    BLOCKED: 0.0,
}


def build_design_test_kit(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build a design-level test kit and run deterministic simulation if possible."""

    body = enrich_payload_with_topology_evidence(dict(payload or {}))
    plan = _resolve_diy_plan(body)
    plan = _close_plan_measurement_gates(plan, body)
    tests: List[Dict[str, Any]] = []

    tests.extend(_plan_availability_tests(plan))
    modules = _modules_from_plan(plan)
    links = _module_links(modules)
    tests.extend(_requirement_tests(plan))
    tests.extend(_module_contract_tests(modules))
    tests.extend(_evidence_gate_tests(plan))

    netlist_payload = _netlist_payload(body)
    compiled_netlist = {}
    netlist_source = "provided_payload" if netlist_payload else "unavailable"
    if not netlist_payload:
        compiled_netlist = compile_topology_to_netlist(body)
        if compiled_netlist.get("available") and isinstance(compiled_netlist.get("netlist"), dict) and compiled_netlist.get("netlist"):
            netlist_payload = compiled_netlist["netlist"]
            netlist_source = "compiled_topology"
        elif _compiler_was_relevant(compiled_netlist):
            netlist_source = "topology_compile_blocked"

    tests.extend(_compiler_tests(compiled_netlist, netlist_source=netlist_source))
    constraints = _constraints_from_payload(body, compiled_netlist)
    simulation = _run_power_tree_simulation(netlist_payload, constraints)
    simulation["load_envelope"] = _run_load_envelope_simulations(compiled_netlist, netlist_payload, constraints)
    tests.extend(_simulation_tests(simulation, netlist_payload))
    tests.extend(_load_envelope_tests(simulation.get("load_envelope") if isinstance(simulation.get("load_envelope"), dict) else {}))

    summary = _summarize_tests(tests)
    release_gate = _release_gate(plan, summary, simulation, compiled_netlist)
    subject = _subject_from_plan(plan, body)
    design_model = {
        "abstraction_level": "netlist_and_module_graph" if netlist_payload else ("module_graph" if modules else "requirements_only"),
        "modules": modules,
        "links": links,
        "simulation_fixture_required": not bool(netlist_payload),
        "simulation_model_source": netlist_source,
        "compiled_topology_netlist": compiled_netlist,
        "simulation_fixture_template": _simulation_fixture_template(plan, modules, body),
        "test_vectors": _test_vectors(plan, modules),
    }

    return {
        "mode": "hardware_design_test_kit",
        "schema_version": SCHEMA_VERSION,
        "available": bool(plan.get("available")) or bool(modules) or bool(netlist_payload),
        "subject": subject,
        "design_model": design_model,
        "test_suite": {
            **summary,
            "tests": tests,
        },
        "simulation": simulation,
        "release_gate": release_gate,
        "next_actions": _next_actions(plan, summary, simulation, netlist_payload, compiled_netlist),
        "claim_boundary": (
            "This test kit can validate requirements, module contracts, evidence gates, and supplied DC power-tree netlists. "
            "It does not authorize arbitrary unknown boards, mains work, battery packs, or production release without measured topology, "
            "bench evidence, and specialist review where hazards apply."
        ),
    }


def _resolve_diy_plan(body: Dict[str, Any]) -> Dict[str, Any]:
    for candidate in [
        body.get("diy_project_engineering"),
        body.get("diy_project_engineering_plan"),
        (body.get("analysis") or {}).get("diy_project_engineering") if isinstance(body.get("analysis"), dict) else None,
    ]:
        if isinstance(candidate, dict) and candidate.get("mode") == "diy_project_engineering":
            return candidate

    hardware_plan = body.get("hardware_plan") if isinstance(body.get("hardware_plan"), dict) else {}
    analysis = hardware_plan.get("analysis") if isinstance(hardware_plan.get("analysis"), dict) else {}
    candidate = analysis.get("diy_project_engineering")
    if isinstance(candidate, dict) and candidate.get("mode") == "diy_project_engineering":
        return candidate

    return build_diy_project_engineering_plan(body)


CORE_MEASUREMENT_GATE_REQUIREMENTS = {
    "power_no_short": {"resistance"},
    "power_voltage_current": {"voltage", "current"},
    "logic_ground": {"continuity", "voltage", "logic"},
    "load_current_thermal": {"current", "thermal"},
    "profile_usb_uart_debug_adapter_1": {"continuity", "voltage", "logic"},
}


def _close_plan_measurement_gates(plan: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(plan, dict) or not plan.get("engineering_gates"):
        return plan
    measurements = _measurement_rows_from_payload(body)
    if not measurements:
        return plan

    closed_ids = set()
    failed_ids = set()
    gates: List[Dict[str, Any]] = []
    for gate in plan.get("engineering_gates") or []:
        if not isinstance(gate, dict):
            continue
        next_gate = dict(gate)
        gate_id = str(next_gate.get("gate_id") or "")
        required = CORE_MEASUREMENT_GATE_REQUIREMENTS.get(gate_id)
        status = str(next_gate.get("status") or "open")
        if next_gate.get("type") != "measurement" or status in {"closed", "pass", "blocked"} or not required:
            gates.append(next_gate)
            continue

        failed = _failed_measurement_for_categories(measurements, required)
        if failed:
            next_gate["status"] = "failed"
            next_gate["result"] = "fail"
            next_gate["closure"] = _measurement_gate_closure(failed, source="structured_measurement_failed")
            failed_ids.add(gate_id)
            gates.append(next_gate)
            continue

        matches = _passed_measurements_by_category(measurements, required)
        if set(matches) >= required:
            next_gate["status"] = "closed"
            next_gate["result"] = "pass"
            next_gate["closure"] = {
                "source": "structured_measurements",
                "required_categories": sorted(required),
                "measurements": [_measurement_gate_closure(row, source="structured_measurement") for row in _dedupe_measurements(matches.values())],
            }
            closed_ids.add(gate_id)
        gates.append(next_gate)

    if not closed_ids and not failed_ids:
        return plan

    next_plan = dict(plan)
    next_plan["engineering_gates"] = gates
    next_plan["next_evidence_tasks"] = [
        task
        for task in plan.get("next_evidence_tasks") or []
        if not isinstance(task, dict) or str(task.get("task_id") or "") not in closed_ids
    ]
    readiness = dict(plan.get("readiness") if isinstance(plan.get("readiness"), dict) else {})
    if readiness:
        open_count = len([gate for gate in gates if str(gate.get("status") or "open") not in {"closed", "pass"}])
        blocked_count = len([gate for gate in gates if gate.get("type") == "safety" or str(gate.get("status") or "") in {"blocked", "failed"}])
        readiness["open_gate_count"] = open_count
        readiness["blocked_gate_count"] = blocked_count
        readiness["measurement_gate_closure_source"] = "structured_topology_measurements"
        next_plan["readiness"] = readiness
    return next_plan


def _measurement_rows_from_payload(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for value in [
        body.get("measurements"),
        (body.get("analysis") or {}).get("measurements") if isinstance(body.get("analysis"), dict) else None,
        (body.get("topology_evidence_bridge") or {}).get("measurement_rows") if isinstance(body.get("topology_evidence_bridge"), dict) else None,
    ]:
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    return _dedupe_measurements(rows)


def _failed_measurement_for_categories(measurements: Sequence[Dict[str, Any]], required: set) -> Optional[Dict[str, Any]]:
    for row in measurements:
        if not _measurement_failed(row):
            continue
        if _measurement_categories(row) & required:
            return row
    return None


def _passed_measurements_by_category(measurements: Sequence[Dict[str, Any]], required: set) -> Dict[str, Dict[str, Any]]:
    matches: Dict[str, Dict[str, Any]] = {}
    for row in measurements:
        if not _measurement_passed(row):
            continue
        for category in sorted(_measurement_categories(row) & required):
            matches.setdefault(category, row)
    return matches


def _measurement_passed(row: Dict[str, Any]) -> bool:
    if _measurement_failed(row):
        return False
    status = str(row.get("status") or row.get("result") or "").lower()
    if status in {"pass", "passed", "ok", "closed", "verified", "measured", "normal"}:
        return True
    if row.get("passed") is True:
        return True
    value = str(row.get("value") or "").strip().lower()
    return bool(value and value not in {"fail", "failed", "unsafe", "short", "shorted"})


def _measurement_failed(row: Dict[str, Any]) -> bool:
    if row.get("failed") is True:
        return True
    status = str(row.get("status") or row.get("result") or "").lower()
    value = str(row.get("value") or "").lower()
    return status in {"fail", "failed", "unsafe", "short", "shorted"} or value in {"fail", "failed", "unsafe", "short", "shorted"}


def _measurement_categories(row: Dict[str, Any]) -> set:
    existing = {str(item) for item in row.get("categories") or [] if str(item).strip()}
    text = " ".join(
        str(row.get(key) or "")
        for key in ["measurement_id", "type", "target", "unit", "value", "notes"]
    ).lower()
    categories = set(existing)
    unit = str(row.get("unit") or "").strip().lower()
    if "voltage" in text or "polarity" in text or unit in {"v", "volt", "volts"} or re.search(r"\b\d+(?:\.\d+)?\s*v\b", text):
        categories.add("voltage")
    if "resistance" in text or "ohm" in text or unit in {"ohm", "ohms"} or "no-short" in text or "no short" in text:
        categories.add("resistance")
    if "continuity" in text or "shared ground" in text or "ground continuity" in text:
        categories.add("continuity")
    if "current" in text or "current-limited" in text or "current limited" in text or unit in {"a", "ma", "amp", "amps"}:
        categories.add("current")
    if any(token in text for token in ["thermal", "temperature", "heat", "hot", "warm"]) or unit in {"c", "°c", "degc", "celsius"}:
        categories.add("thermal")
    if any(token in text for token in ["logic", "serial", "uart", "i2c", "spi", "idle", "tx", "rx", "scl", "sda"]):
        categories.add("logic")
    return categories


def _measurement_gate_closure(row: Dict[str, Any], *, source: str) -> Dict[str, Any]:
    return {
        "source": source,
        "measurement_id": row.get("measurement_id"),
        "measurement_type": row.get("type"),
        "target": row.get("target"),
        "value": row.get("value"),
        "unit": row.get("unit"),
        "notes": row.get("notes"),
        "confidence": row.get("confidence"),
    }


def _dedupe_measurements(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = (
            str(row.get("measurement_id") or ""),
            str(row.get("type") or ""),
            str(row.get("target") or ""),
            str(row.get("value") or ""),
            str(row.get("unit") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(row))
    return result


def _plan_availability_tests(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    if plan.get("available"):
        return [
            _test(
                "plan_available",
                "requirements",
                PASS,
                "DIY engineering plan is available.",
                "The test kit has a structured project intent, requirements, architecture blocks, and evidence gates to test.",
                source="diy_project_engineering",
            )
        ]
    status = _unavailable_plan_status(plan)
    return [
        _test(
            "plan_unavailable",
            "requirements",
            status,
            "No testable DIY engineering plan was produced.",
            str(plan.get("reason") or "The input needs a build goal, hardware target, or explicit design artifact before tests can be generated."),
            evidence_required=["build goal or design payload"],
            source="diy_project_engineering",
        )
    ]


def _unavailable_plan_status(plan: Dict[str, Any]) -> str:
    reason = str(plan.get("reason") or "").lower()
    if any(word in reason for word in ["safety", "specialist", "hazard", "mains", "high-voltage", "high voltage"]):
        return BLOCKED
    return PENDING


def _requirement_tests(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    requirements = plan.get("requirements") if isinstance(plan.get("requirements"), dict) else {}
    functional = [row for row in requirements.get("functional_requirements") or [] if isinstance(row, dict)]
    required_caps = [str(cap) for cap in requirements.get("required_capabilities") or [] if str(cap)]
    tests = [
        _test(
            "functional_requirements_defined",
            "requirements",
            PASS if functional else PENDING,
            "Functional requirements are defined.",
            "At least one terminal output function and its evidence need are present." if functional else "Define terminal behavior before accepting a schematic or splice.",
            evidence_required=[] if functional else ["terminal output function", "pass/fail behavior"],
            source="diy_project_engineering",
        ),
        _test(
            "required_capabilities_defined",
            "requirements",
            PASS if required_caps else PENDING,
            "Required capabilities are enumerated.",
            ", ".join(required_caps) if required_caps else "The engine needs required capabilities before module coverage can be trusted.",
            evidence_required=[] if required_caps else ["required capability list"],
            source="diy_project_engineering",
        ),
    ]
    return tests


def _modules_from_plan(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for block in plan.get("architecture_blocks") or []:
        if not isinstance(block, dict):
            continue
        rows.append(
            {
                "module_id": str(block.get("block_id") or _safe_id(block.get("role") or "module")),
                "role": str(block.get("role") or ""),
                "required_capabilities": [str(cap) for cap in block.get("required_capabilities") or []],
                "candidate_resource_ids": [str(resource_id) for resource_id in block.get("candidate_resource_ids") or []],
                "status": str(block.get("status") or "unknown"),
            }
        )
    return rows


def _module_contract_tests(modules: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not modules:
        return [
            _test(
                "module_graph_missing",
                "module_graph",
                PENDING,
                "Module graph is not available.",
                "A schematic/splice test needs at least a module graph or a supplied netlist.",
                evidence_required=["module list or netlist"],
                source="design_test_kit",
            )
        ]

    tests = [
        _test(
            "module_graph_present",
            "module_graph",
            PASS,
            "Module graph is available.",
            f"{len(modules)} modules were extracted from the engineering plan.",
            source="diy_project_engineering",
        )
    ]
    for module in modules:
        status = str(module.get("status") or "")
        module_id = str(module.get("module_id") or "module")
        if status == "blocked_until_specialist_authority":
            tests.append(
                _test(
                    f"module_{module_id}_blocked",
                    "module_graph",
                    BLOCKED,
                    f"{module_id} is blocked by specialist authority.",
                    "The module cannot be wired, powered, or released through the direct DIY/splice path.",
                    evidence_required=["specialist authority packet"],
                    source="diy_project_engineering",
                )
            )
        elif status == "missing_resource":
            tests.append(
                _test(
                    f"module_{module_id}_resource_missing",
                    "module_graph",
                    FAIL,
                    f"{module_id} has no covered resource.",
                    "The design cannot be considered complete until this module's capability is supplied by an owned, salvaged, designed, or purchasable resource.",
                    evidence_required=["resource covering module capability"],
                    source="diy_project_engineering",
                )
            )
        elif status == "resource_selected_evidence_gated":
            tests.append(
                _test(
                    f"module_{module_id}_resource_selected",
                    "module_graph",
                    PENDING,
                    f"{module_id} has a selected resource but still needs evidence.",
                    "Selected resources are plausible, but the module is not trusted until ratings, pinout, and behavior are measured or documented.",
                    evidence_required=["ratings", "pinout", "bench measurement"],
                    source="diy_project_engineering",
                )
            )
        else:
            tests.append(
                _test(
                    f"module_{module_id}_contract_review",
                    "module_graph",
                    WARNING,
                    f"{module_id} needs interface contract review.",
                    "The module exists, but its exact electrical interface is not yet represented as a measured contract.",
                    evidence_required=["interface contract"],
                    source="design_test_kit",
                )
            )
    return tests


def _evidence_gate_tests(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    gates = [gate for gate in plan.get("engineering_gates") or [] if isinstance(gate, dict)]
    if not gates:
        return [
            _test(
                "evidence_gates_missing",
                "evidence",
                PENDING,
                "Evidence gates are not available.",
                "Bench proof, measurement, and safety gates must exist before a design can become trustworthy.",
                evidence_required=["engineering gates"],
                source="design_test_kit",
            )
        ]

    tests = []
    safety_gates = [gate for gate in gates if gate.get("type") == "safety"]
    blocked_safety = [gate for gate in safety_gates if str(gate.get("status") or "open") == "blocked"]
    tests.append(
        _test(
            "safety_authority_gate",
            "safety",
            BLOCKED if blocked_safety else PASS,
            "Safety authority gate is evaluated.",
            blocked_safety[0].get("prompt") if blocked_safety else "No hard specialist-authority gate is active in the current plan.",
            evidence_required=["specialist authority"] if blocked_safety else [],
            source="diy_project_engineering",
        )
    )

    for gate in gates[:24]:
        status = str(gate.get("status") or "open")
        gate_id = str(gate.get("gate_id") or _safe_id(gate.get("prompt") or "gate"))
        gate_type = str(gate.get("type") or "review")
        if status in {"closed", "pass"}:
            test_status = PASS
        elif gate_type == "safety" and status == "blocked":
            test_status = BLOCKED
        elif gate_type == "measurement":
            test_status = PENDING
        elif gate_type == "outcome":
            test_status = PENDING
        else:
            test_status = WARNING
        tests.append(
            _test(
                f"gate_{gate_id}",
                "evidence" if gate_type != "safety" else "safety",
                test_status,
                f"{gate_type} gate: {gate_id}",
                str(gate.get("prompt") or ""),
                evidence_required=[] if test_status == PASS else [_gate_evidence_name(gate_type)],
                source=str(gate.get("source") or "diy_project_engineering"),
            )
        )
    return _dedupe_tests(tests)


def _netlist_payload(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for key in ["netlist", "simulation_netlist", "design_netlist", "power_tree_netlist"]:
        value = body.get(key)
        if isinstance(value, dict):
            return value
    for parent_key in ["simulation", "test_kit", "design", "schematic"]:
        parent = body.get(parent_key)
        if not isinstance(parent, dict):
            continue
        for key in ["netlist", "simulation_netlist", "design_netlist", "power_tree_netlist"]:
            value = parent.get(key)
            if isinstance(value, dict):
                return value
    return None


def _compiler_was_relevant(compiled_netlist: Dict[str, Any]) -> bool:
    if not compiled_netlist:
        return False
    issues = compiled_netlist.get("issues") if isinstance(compiled_netlist.get("issues"), list) else []
    return bool(compiled_netlist.get("available") or any(row.get("issue_id") != "topology_unavailable" for row in issues if isinstance(row, dict)))


def _compiler_tests(compiled_netlist: Dict[str, Any], *, netlist_source: str) -> List[Dict[str, Any]]:
    if not _compiler_was_relevant(compiled_netlist):
        return []
    coverage = compiled_netlist.get("coverage") if isinstance(compiled_netlist.get("coverage"), dict) else {}
    tests = [
        _test(
            "topology_netlist_compiler_ran",
            "power_simulation",
            PASS if compiled_netlist.get("available") else FAIL,
            "Topology-to-netlist compiler produced a simulation model.",
            (
                f"Compiler source: {compiled_netlist.get('source')}; coverage score {coverage.get('score')}."
                if compiled_netlist.get("available")
                else "Topology evidence was present but could not be compiled into a usable low-voltage DC model."
            ),
            evidence_required=[] if compiled_netlist.get("available") else ["measured low-voltage power and ground topology"],
            source="topology_netlist_compiler",
        )
    ]
    dimensions = coverage.get("dimensions") if isinstance(coverage.get("dimensions"), dict) else {}
    if dimensions:
        tests.append(
            _test(
                "topology_netlist_coverage",
                "power_simulation",
                PASS if coverage.get("simulation_ready") else WARNING,
                "Compiled topology model coverage is evaluated.",
                ", ".join(f"{key}={bool(value)}" for key, value in dimensions.items()),
                evidence_required=[] if coverage.get("simulation_ready") else ["numeric load current model"],
                source="topology_netlist_compiler",
            )
        )
    for issue in compiled_netlist.get("issues") or []:
        if not isinstance(issue, dict) or issue.get("issue_id") == "topology_unavailable":
            continue
        severity = str(issue.get("severity") or "warning").lower()
        status = BLOCKED if severity == "critical" else FAIL if severity == "error" else WARNING
        tests.append(
            _test(
                f"topology_compile_{issue.get('issue_id')}",
                "power_simulation",
                status,
                str(issue.get("summary") or "Topology compile issue"),
                str(issue.get("detail") or ""),
                evidence_required=["topology measurement or load model"] if status in {FAIL, WARNING} else ["hazard clearance"],
                source=str(issue.get("source") or "topology_netlist_compiler"),
            )
        )
    if netlist_source == "compiled_topology":
        tests.append(
            _test(
                "topology_netlist_selected_for_simulation",
                "power_simulation",
                PASS,
                "Compiled topology netlist was selected for simulation.",
                "No explicit netlist was supplied, so the test kit used the topology compiler output.",
                source="topology_netlist_compiler",
            )
        )
    return _dedupe_tests(tests)


def _constraints_from_payload(body: Dict[str, Any], compiled_netlist: Optional[Dict[str, Any]] = None) -> PowerTreeConstraints:
    raw = {}
    if isinstance(compiled_netlist, dict) and isinstance(compiled_netlist.get("constraints"), dict):
        raw.update(compiled_netlist["constraints"])
    for key in ["simulation_constraints", "test_constraints", "power_tree_constraints"]:
        if isinstance(body.get(key), dict):
            raw.update(body[key])
            break
    if not raw and isinstance(body.get("constraints"), dict):
        raw.update(body["constraints"])
    for parent_key in ["simulation", "test_kit", "design", "schematic"]:
        parent = body.get(parent_key)
        if isinstance(parent, dict) and isinstance(parent.get("constraints"), dict):
            raw = {**raw, **parent["constraints"]}

    source_limits = []
    for row in _rows(raw.get("source_limits") or raw.get("source_current_limits")):
        if not isinstance(row, dict):
            continue
        name = row.get("source_name") or row.get("name") or row.get("source")
        limit = _first_float(row.get("max_current_a"), row.get("current_limit_a"), row.get("max_a"), row.get("amps"))
        if name and limit is not None:
            source_limits.append(SourceCurrentLimit(source_name=str(name), max_current_a=limit))

    max_trace_drop = _first_float(raw.get("max_trace_drop_v"), raw.get("trace_drop_limit_v"))
    return PowerTreeConstraints(source_limits=source_limits, max_trace_drop_v=max_trace_drop if max_trace_drop is not None else 0.25)


def _run_power_tree_simulation(netlist_payload: Optional[Dict[str, Any]], constraints: PowerTreeConstraints) -> Dict[str, Any]:
    if not netlist_payload:
        return {
            "available": False,
            "engine": "not_supplied",
            "status": "not_run",
            "results": {},
            "issues": [],
            "reason": "No structured netlist was supplied for deterministic DC power-tree validation.",
        }

    try:
        netlist = netlist_from_dict(netlist_payload)
        results, issues = validate_pcb_power_tree(netlist, constraints=constraints)
    except Exception as exc:
        return {
            "available": True,
            "engine": "dc_power_tree_validator",
            "status": "failed_to_run",
            "results": {},
            "issues": [
                {
                    "severity": "error",
                    "component": "netlist",
                    "issue": "Simulation failed to run",
                    "explanation": str(exc),
                    "physics_data": {},
                    "solution": "Fix the netlist schema, topology, or solver constraints and rerun the test kit.",
                }
            ],
        }

    return {
        "available": True,
        "engine": "dc_power_tree_validator",
        "status": "completed",
        "constraints": {
            "source_limits": [{"source_name": limit.source_name, "max_current_a": limit.max_current_a} for limit in constraints.source_limits],
            "max_trace_drop_v": constraints.max_trace_drop_v,
        },
        "results": _serialize_power_tree_results(results),
        "issues": [_serialize_issue(issue) for issue in issues],
    }


def _run_load_envelope_simulations(
    compiled_netlist: Dict[str, Any],
    base_netlist_payload: Optional[Dict[str, Any]],
    constraints: PowerTreeConstraints,
) -> Dict[str, Any]:
    if not isinstance(compiled_netlist, dict) or not isinstance(base_netlist_payload, dict):
        return {"available": False, "status": "not_available", "reason": "No compiled topology netlist was available for load-envelope simulation.", "scenarios": []}
    envelope = compiled_netlist.get("load_envelope") if isinstance(compiled_netlist.get("load_envelope"), dict) else {}
    if not envelope.get("available") or envelope.get("mode") != "bounded_unknown_load":
        return {
            "available": False,
            "status": "not_required" if envelope.get("mode") == "measured_load_model" else "not_available",
            "reason": envelope.get("reason") or "A bounded unknown-load envelope was not available.",
            "scenarios": [],
        }

    rows = []
    fail_count = 0
    warning_count = 0
    for scenario in envelope.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        netlist = _netlist_with_envelope_load(base_netlist_payload, scenario)
        result = _run_power_tree_simulation(netlist, constraints)
        issues = result.get("issues") if isinstance(result.get("issues"), list) else []
        hard = [issue for issue in issues if str(issue.get("severity") or "").lower() in {"critical", "error"}]
        warnings = [issue for issue in issues if str(issue.get("severity") or "").lower() == "warning"]
        fail_count += 1 if hard else 0
        warning_count += 1 if warnings and not hard else 0
        sim_results = result.get("results") if isinstance(result.get("results"), dict) else {}
        rows.append(
            {
                "scenario_id": scenario.get("scenario_id"),
                "load_current_a": scenario.get("load_current_a"),
                "nominal_power_w": scenario.get("nominal_power_w"),
                "purpose": scenario.get("purpose"),
                "status": "fail" if hard else "warning" if warnings else "pass",
                "node_v": sim_results.get("node_v") or {},
                "vsource_i": sim_results.get("vsource_i") or {},
                "issues": issues,
            }
        )

    return {
        "available": True,
        "status": "fail" if fail_count else "warning" if warning_count else "pass",
        "mode": envelope.get("mode"),
        "source_name": envelope.get("source_name"),
        "node": envelope.get("node"),
        "absolute_source_limit_a": envelope.get("absolute_source_limit_a"),
        "recommended_max_load_a": envelope.get("recommended_max_load_a"),
        "recommended_max_power_w": envelope.get("recommended_max_power_w"),
        "pass_condition": envelope.get("pass_condition"),
        "measurement_prompt": envelope.get("measurement_prompt"),
        "scenario_count": len(rows),
        "fail_count": fail_count,
        "warning_count": warning_count,
        "scenarios": rows,
        "claim_boundary": envelope.get("claim_boundary"),
    }


def _netlist_with_envelope_load(base_netlist_payload: Dict[str, Any], scenario: Dict[str, Any]) -> Dict[str, Any]:
    netlist = {
        "version": base_netlist_payload.get("version", 1),
        "resistors": list(base_netlist_payload.get("resistors") or []),
        "current_sources": list(base_netlist_payload.get("current_sources") or []),
        "voltage_sources": list(base_netlist_payload.get("voltage_sources") or []),
        "traces": list(base_netlist_payload.get("traces") or []),
        "ldos": list(base_netlist_payload.get("ldos") or []),
        "loads_cc": list(base_netlist_payload.get("loads_cc") or []),
        "loads_cp": list(base_netlist_payload.get("loads_cp") or []),
        "voltage_constraints": list(base_netlist_payload.get("voltage_constraints") or []),
    }
    load_current = _first_float(scenario.get("load_current_a")) or 0.0
    if load_current > 0 and not netlist["loads_cc"]:
        netlist["loads_cc"].append(
            {
                "name": f"envelope_{_safe_id(scenario.get('scenario_id') or 'load')}",
                "node": str(scenario.get("node") or "VBUS"),
                "amps": load_current,
                "gnd": "0",
                "min_v_off": None,
            }
        )
    return netlist


def _simulation_tests(simulation: Dict[str, Any], netlist_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not netlist_payload:
        return [
            _test(
                "dc_power_tree_netlist_required",
                "power_simulation",
                PENDING,
                "DC power-tree simulation fixture is required.",
                "Supply a versioned netlist with sources, loads, rails/traces, and voltage constraints to run deterministic simulation.",
                evidence_required=["versioned netlist", "source current limits", "voltage constraints"],
                source="design_test_kit",
            )
        ]

    tests = []
    issues = simulation.get("issues") or []
    if simulation.get("status") == "failed_to_run":
        return [
            _test(
                "dc_power_tree_simulation_failed",
                "power_simulation",
                FAIL,
                "DC power-tree simulation failed to run.",
                issues[0].get("explanation") if issues else "Simulation could not complete.",
                evidence_required=["valid netlist"],
                source="dc_power_tree_validator",
            )
        ]

    results = simulation.get("results") if isinstance(simulation.get("results"), dict) else {}
    tests.append(
        _test(
            "dc_power_tree_solver_completed",
            "power_simulation",
            PASS if results.get("converged") else WARNING,
            "DC power-tree solver completed.",
            "Solver converged." if results.get("converged") else "Solver completed but did not converge within the configured iteration limit.",
            evidence_required=[] if results.get("converged") else ["simplified or corrected netlist"],
            source="dc_power_tree_validator",
        )
    )
    if not issues:
        tests.append(
            _test(
                "dc_power_tree_no_validator_issues",
                "power_simulation",
                PASS,
                "No power-tree validator issues were reported.",
                "Source current, voltage constraints, trace drop, regulator, and power-balance checks passed for the supplied model.",
                source="dc_power_tree_validator",
            )
        )
        return tests

    for index, issue in enumerate(issues, start=1):
        severity = str(issue.get("severity") or "warning").lower()
        status = FAIL if severity in {"critical", "error"} else WARNING
        tests.append(
            _test(
                f"dc_power_tree_issue_{index}_{_safe_id(issue.get('component') or issue.get('issue'))}",
                "power_simulation",
                status,
                str(issue.get("issue") or "Power-tree issue"),
                str(issue.get("explanation") or ""),
                evidence_required=["netlist correction", "bench measurement"],
                source="dc_power_tree_validator",
                data={"component": issue.get("component"), "physics_data": issue.get("physics_data") or {}, "solution": issue.get("solution")},
            )
        )
    return tests


def _load_envelope_tests(load_envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not load_envelope.get("available"):
        return []
    tests = [
        _test(
            "bounded_load_envelope_available",
            "power_simulation",
            PASS if load_envelope.get("status") == "pass" else FAIL if load_envelope.get("status") == "fail" else WARNING,
            "Bounded unknown-load envelope was simulated.",
            str(load_envelope.get("pass_condition") or "Measured load current must stay inside the derived source budget."),
            evidence_required=["real load steady current", "startup/inrush current"],
            source="topology_netlist_compiler",
        )
    ]
    for scenario in load_envelope.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        status = str(scenario.get("status") or "warning")
        tests.append(
            _test(
                f"bounded_load_envelope_{scenario.get('scenario_id')}",
                "power_simulation",
                PASS if status == "pass" else FAIL if status == "fail" else WARNING,
                f"Envelope scenario {scenario.get('scenario_id')} at {scenario.get('load_current_a')}A.",
                f"Node voltages: {scenario.get('node_v') or {}}; source currents: {scenario.get('vsource_i') or {}}",
                evidence_required=[] if status == "pass" else ["corrected source/load/trace model"],
                source="dc_power_tree_validator",
            )
        )
    return _dedupe_tests(tests)


def _subject_from_plan(plan: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    intent = plan.get("project_intent") if isinstance(plan.get("project_intent"), dict) else {}
    readiness = plan.get("readiness") if isinstance(plan.get("readiness"), dict) else {}
    return {
        "goal": intent.get("goal") or body.get("diy_project") or body.get("goal") or body.get("description") or "",
        "profile_id": intent.get("profile_id"),
        "profile_label": intent.get("profile_label"),
        "readiness": readiness.get("level"),
        "readiness_score": readiness.get("score"),
    }


def _module_links(modules: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {str(module.get("module_id")): module for module in modules}
    links: List[Dict[str, Any]] = []

    power_ids = [module_id for module_id, module in by_id.items() if "power" in module_id or "power" in set(module.get("required_capabilities") or [])]
    controller_ids = [
        module_id
        for module_id, module in by_id.items()
        if "controller" in module_id or "controller" in set(module.get("required_capabilities") or [])
    ]
    load_ids = [
        module_id
        for module_id, module in by_id.items()
        if set(module.get("required_capabilities") or []) & {"motor_or_load", "fan_or_pump", "led_or_light", "speaker_or_audio"}
    ]
    driver_ids = [
        module_id
        for module_id, module in by_id.items()
        if set(module.get("required_capabilities") or []) & {"actuator_driver", "protection"}
    ]
    sensor_ids = [
        module_id
        for module_id, module in by_id.items()
        if set(module.get("required_capabilities") or []) & {"sensor_or_adc", "switch_or_button", "camera_or_vision"}
    ]

    for power_id in power_ids[:2]:
        for module_id in by_id:
            if module_id != power_id:
                links.append(_link(power_id, module_id, "power_or_ground_contract"))
    for controller_id in controller_ids[:2]:
        for sensor_id in sensor_ids[:4]:
            if sensor_id != controller_id:
                links.append(_link(sensor_id, controller_id, "signal_input_contract"))
        for driver_id in driver_ids[:4]:
            if driver_id != controller_id:
                links.append(_link(controller_id, driver_id, "control_signal_contract"))
    for driver_id in driver_ids[:4]:
        for load_id in load_ids[:4]:
            if load_id != driver_id:
                links.append(_link(driver_id, load_id, "switched_load_contract"))

    if not links and len(modules) > 1:
        for left, right in zip(modules, modules[1:]):
            links.append(_link(str(left.get("module_id")), str(right.get("module_id")), "sequence_contract"))
    return _dedupe_links(links)[:24]


def _simulation_fixture_template(plan: Dict[str, Any], modules: Sequence[Dict[str, Any]], body: Dict[str, Any]) -> Dict[str, Any]:
    requirements = plan.get("requirements") if isinstance(plan.get("requirements"), dict) else {}
    required_caps = [str(cap) for cap in requirements.get("required_capabilities") or []]
    source_name = "VUSB" if "usb" in " ".join([str(body.get("diy_project") or ""), str(body.get("project_brief") or "")]).lower() else "VSUPPLY"
    load_modules = [
        module
        for module in modules
        if set(module.get("required_capabilities") or []) & {"motor_or_load", "fan_or_pump", "led_or_light", "speaker_or_audio", "display_or_ui"}
    ]
    voltage_node = "VBUS"
    return {
        "schema": "src.engines.netlist_io version 1",
        "minimum_netlist": {
            "version": 1,
            "voltage_sources": [{"name": source_name, "n_plus": voltage_node, "n_minus": "0", "volts": 5.0}],
            "loads_cc": [
                {
                    "name": _safe_id(module.get("module_id") or "load"),
                    "node": voltage_node,
                    "amps": None,
                    "gnd": "0",
                    "min_v_off": 3.0,
                }
                for module in load_modules[:6]
            ],
            "voltage_constraints": [{"name": "main_rail_window", "node": voltage_node, "gnd": "0", "min_v": 4.5, "max_v": 5.5}],
            "resistors": [],
            "current_sources": [],
            "traces": [],
            "ldos": [],
            "loads_cp": [],
        },
        "required_measurements": _dedupe_text(
            [
                "source voltage and current limit",
                "no-short resistance from each rail to ground",
                "load startup current",
                "load steady current",
                "rail voltage under load",
                "thermal behavior after duty-cycle run",
            ]
        ),
        "capabilities_to_model": required_caps,
    }


def _test_vectors(plan: Dict[str, Any], modules: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    requirements = plan.get("requirements") if isinstance(plan.get("requirements"), dict) else {}
    caps = set(requirements.get("required_capabilities") or [])
    vectors = [
        {
            "vector_id": "first_power_current_limited",
            "layer": "bench",
            "purpose": "Prove source polarity, rail voltage, and no-short state before integration.",
            "expected_evidence": ["rail voltage", "source current limit", "no-short measurement"],
        },
        {
            "vector_id": "dc_power_tree_loaded",
            "layer": "simulation",
            "purpose": "Simulate rail voltage, source current, trace drop, regulator stress, and load draw.",
            "expected_evidence": ["versioned netlist", "source limits", "load current model"],
        },
        {
            "vector_id": "terminal_output_function",
            "layer": "functional",
            "purpose": "Run the target behavior and record pass/fail output evidence.",
            "expected_evidence": ["output proof", "test log"],
        },
    ]
    if caps & {"controller", "sensor_or_adc"}:
        vectors.append(
            {
                "vector_id": "input_truth_table",
                "layer": "functional",
                "purpose": "Prove sensor/input range, idle state, threshold behavior, and controller interpretation.",
                "expected_evidence": ["input readings", "threshold log"],
            }
        )
    if caps & {"actuator_driver", "motor_or_load", "fan_or_pump"}:
        vectors.append(
            {
                "vector_id": "load_driver_duty_cycle",
                "layer": "bench",
                "purpose": "Prove startup current, steady current, flyback/protection, and thermal margin under repeated switching.",
                "expected_evidence": ["startup current", "steady current", "temperature observation"],
            }
        )
    if modules:
        vectors.append(
            {
                "vector_id": "module_interface_contracts",
                "layer": "module_graph",
                "purpose": "Confirm every module edge has named power, ground, signal, connector, pinout, and rating contracts.",
                "expected_evidence": ["interface contract list"],
            }
        )
    return vectors


def _summarize_tests(tests: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {status: 0 for status in [PASS, WARNING, FAIL, BLOCKED, PENDING]}
    for test in tests:
        status = str(test.get("status") or PENDING)
        counts[status] = counts.get(status, 0) + 1
    total = max(1, len(tests))
    score = sum(STATUS_WEIGHT.get(str(test.get("status") or PENDING), 0.0) for test in tests) / total
    if counts[BLOCKED]:
        score = min(score, 0.25)
    elif counts[FAIL]:
        score = min(score, 0.45)
    return {
        "total_count": len(tests),
        "pass_count": counts.get(PASS, 0),
        "warning_count": counts.get(WARNING, 0),
        "fail_count": counts.get(FAIL, 0),
        "blocked_count": counts.get(BLOCKED, 0),
        "pending_count": counts.get(PENDING, 0),
        "score": round(score, 3),
    }


def _release_gate(
    plan: Dict[str, Any],
    summary: Dict[str, Any],
    simulation: Dict[str, Any],
    compiled_netlist: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    readiness = plan.get("readiness") if isinstance(plan.get("readiness"), dict) else {}
    compiled_coverage = (
        compiled_netlist.get("coverage")
        if isinstance(compiled_netlist, dict) and isinstance(compiled_netlist.get("coverage"), dict)
        else {}
    )
    compiled_envelope = (
        compiled_netlist.get("load_envelope")
        if isinstance(compiled_netlist, dict) and isinstance(compiled_netlist.get("load_envelope"), dict)
        else {}
    )
    simulated_envelope = simulation.get("load_envelope") if isinstance(simulation.get("load_envelope"), dict) else {}
    if summary.get("blocked_count"):
        decision = "blocked_by_safety_or_specialist_authority"
        reason = "At least one safety or specialist-authority gate blocks direct design execution."
    elif any(str(issue.get("severity") or "").lower() in {"critical", "error"} for issue in simulation.get("issues") or []):
        decision = "blocked_by_simulation_failure"
        reason = "The supplied netlist has a deterministic power-tree failure."
    elif simulated_envelope.get("available") and simulated_envelope.get("status") == "fail":
        decision = "blocked_by_simulation_failure"
        reason = "The bounded load-envelope simulation found a deterministic power-tree failure."
    elif summary.get("fail_count"):
        decision = "blocked_by_design_contract"
        reason = "A required module/resource/design contract is missing or failed."
    elif not simulation.get("available"):
        decision = "test_fixture_required"
        reason = "The module-level test suite exists, but a versioned netlist is required before deterministic simulation."
    elif compiled_coverage and not compiled_coverage.get("simulation_ready", True) and compiled_envelope.get("available"):
        decision = "bounded_load_envelope_measurement_required"
        reason = (
            "A topology netlist was compiled without measured load current, but a bounded source-limit envelope is available. "
            "The real load must be measured against that envelope before loaded proof."
        )
    elif compiled_coverage and not compiled_coverage.get("simulation_ready", True):
        decision = "simulation_model_incomplete_load_model_required"
        reason = "A topology netlist was compiled, but it lacks numeric load-current evidence, so loaded power behavior is not proven."
    elif summary.get("pending_count") or summary.get("warning_count"):
        decision = "simulation_passed_bench_evidence_required"
        reason = "Simulation did not find hard failures, but bench evidence and interface contracts remain open."
    else:
        decision = "design_test_suite_passed_bench_release_required"
        reason = "All generated design tests passed for the supplied model; release still needs bench artifact review."

    hard_blocked = decision.startswith("blocked")
    return {
        "decision": decision,
        "can_advance_to_simulation_fixture": not summary.get("blocked_count"),
        "can_advance_to_controlled_bench": not hard_blocked and bool(plan.get("available")),
        "can_power_or_splice": bool(readiness.get("can_build_or_power_now")) and not hard_blocked and summary.get("fail_count", 0) == 0,
        "can_production_release": False,
        "reason": reason,
    }


def _next_actions(
    plan: Dict[str, Any],
    summary: Dict[str, Any],
    simulation: Dict[str, Any],
    netlist_payload: Optional[Dict[str, Any]],
    compiled_netlist: Optional[Dict[str, Any]] = None,
) -> List[str]:
    actions: List[str] = []
    if summary.get("blocked_count"):
        actions.append("Resolve the hard safety or specialist-authority gate before any direct DIY/splice execution.")
    if summary.get("fail_count"):
        actions.append("Close failed module/resource contracts before treating the design as complete.")
    if not netlist_payload:
        actions.append("Fill the simulation fixture with measured source voltage, source current limit, load current, trace/regulator model, and rail constraints.")
    elif any(str(issue.get("severity") or "").lower() in {"critical", "error"} for issue in simulation.get("issues") or []):
        actions.append("Correct the failing netlist condition, then rerun the design test kit before bench power.")
    elif isinstance(compiled_netlist, dict):
        coverage = compiled_netlist.get("coverage") if isinstance(compiled_netlist.get("coverage"), dict) else {}
        if coverage and not coverage.get("simulation_ready", True):
            envelope = compiled_netlist.get("load_envelope") if isinstance(compiled_netlist.get("load_envelope"), dict) else {}
            if envelope.get("available"):
                actions.append(
                    "Measure the real load current and keep steady current <= "
                    f"{envelope.get('recommended_max_load_a')}A; startup/current-limit behavior must stay <= "
                    f"{envelope.get('absolute_source_limit_a')}A."
                )
            else:
                actions.append("Measure or supply numeric load current before treating the topology-derived simulation as a loaded proof.")

    open_tasks = [task for task in plan.get("next_evidence_tasks") or [] if isinstance(task, dict)]
    for task in open_tasks[:3]:
        prompt = str(task.get("prompt") or "").strip()
        if prompt:
            actions.append(prompt)
    actions.append("Record terminal outcome proof only after simulation and bench evidence agree.")
    return _dedupe_text(actions)[:8]


def _serialize_power_tree_results(results: Dict[str, Any]) -> Dict[str, Any]:
    solution = results.get("solution")
    return {
        "converged": bool(results.get("converged")),
        "iterations": int(results.get("iterations") or 0),
        "node_v": _round_map(getattr(solution, "node_v", {})),
        "vsource_i": _round_map(getattr(solution, "vsource_i", {})),
        "resistor_i": _round_map(getattr(solution, "resistor_i", {})),
        "resistor_p": _round_map(getattr(solution, "resistor_p", {})),
        "power_report": _round_map(results.get("power_report") or {}),
    }


def _serialize_issue(issue: Any) -> Dict[str, Any]:
    return {
        "severity": str(getattr(issue, "severity", "warning")),
        "component": str(getattr(issue, "component", "")),
        "issue": str(getattr(issue, "issue", "")),
        "explanation": str(getattr(issue, "explanation", "")),
        "physics_data": getattr(issue, "physics_data", {}) or {},
        "solution": str(getattr(issue, "solution", "")),
    }


def _test(
    test_id: str,
    layer: str,
    status: str,
    check: str,
    rationale: str,
    *,
    evidence_required: Optional[Sequence[str]] = None,
    source: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row = {
        "test_id": _safe_id(test_id),
        "layer": layer,
        "status": status,
        "severity": _severity_for_status(status),
        "check": check,
        "rationale": rationale,
        "evidence_required": list(evidence_required or []),
        "source": source,
    }
    if data:
        row["data"] = data
    return row


def _severity_for_status(status: str) -> str:
    return {
        PASS: "info",
        WARNING: "warning",
        PENDING: "pending",
        FAIL: "error",
        BLOCKED: "critical",
    }.get(status, "pending")


def _gate_evidence_name(gate_type: str) -> str:
    return {
        "measurement": "measurement record",
        "safety": "safety authority record",
        "outcome": "terminal outcome artifact",
        "review": "review artifact",
    }.get(gate_type, "evidence artifact")


def _link(source: str, target: str, contract: str) -> Dict[str, Any]:
    return {"source_module_id": source, "target_module_id": target, "contract_type": contract, "status": "contract_required"}


def _dedupe_tests(tests: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    rows = []
    for test in tests:
        key = str(test.get("test_id") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append(test)
    return rows


def _dedupe_links(links: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    rows = []
    for link in links:
        key = (link.get("source_module_id"), link.get("target_module_id"), link.get("contract_type"))
        if key in seen:
            continue
        seen.add(key)
        rows.append(link)
    return rows


def _dedupe_text(values: Iterable[str]) -> List[str]:
    seen = set()
    rows = []
    for value in values:
        text = str(value or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        rows.append(text)
    return rows


def _rows(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return [value]
    return [value]


def _first_float(*values: Any) -> Optional[float]:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _round_map(values: Dict[str, Any]) -> Dict[str, Any]:
    rounded = {}
    for key, value in values.items():
        if isinstance(value, (int, float)):
            rounded[key] = round(float(value), 6)
        else:
            rounded[key] = value
    return rounded


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:120] or "item"
