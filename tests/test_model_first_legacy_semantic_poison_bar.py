from __future__ import annotations

import json

import hardware_splicer.change_impact as impact_module
import hardware_splicer.circuit_synthesis.planner as circuit_planner
import hardware_splicer.integrations.llm_policy as llm_policy
import hardware_splicer.module_resolver as legacy_resolver
import hardware_splicer.module_resolution_truth as identity_truth
import hardware_splicer.robot_topology as topology_module
from hardware_splicer.change_impact import build_change_impact_graph
from hardware_splicer.circuit_synthesis.planner import plan_circuit
from hardware_splicer.circuit_synthesis.semantic_planner_selector import (
    parse_semantic_planner_selection,
)
from hardware_splicer.module_resolution_truth import (
    fill_capability_gaps,
    resolve_inventory_identity,
)
from hardware_splicer.robot_topology import build_robot_topology
from hardware_splicer.semantic_impact_scope import parse_impact_scope_proposal


def _explode(label: str):
    def fail(*args, **kwargs):
        raise AssertionError(f"model-first path executed demoted legacy semantic function: {label}")

    return fail


def test_model_first_circuit_dispatch_never_executes_keyword_dispatcher(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(circuit_planner, "_legacy_plan_circuit", _explode("circuit_keyword_dispatch"))
    monkeypatch.setattr(
        circuit_planner,
        "select_semantic_circuit_planner",
        lambda intent, llm_callable=None: parse_semantic_planner_selection(
            {
                "selected_planner": "sensor_interface",
                "rationale": "Bounded interface planner selected from structured requirements.",
                "unresolved_questions": [],
                "assumptions": [],
                "authority_effect": "none",
                "automatic_execution": False,
            }
        ),
    )

    candidate = plan_circuit(
        {
            "goal": "battery motor relay H-bridge words deliberately try to poison routing",
            "signal_requirements": [{"type": "i2c"}],
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "bme280"],
            "required_evidence": ["i2c_pullups"],
        }
    )

    assert candidate.metadata["dispatch"]["selection_source"] == "semantic_typed_selection"
    assert candidate.metadata["dispatch"]["legacy_keyword_dispatch_used"] is False


def test_model_first_topology_never_executes_name_keyword_role_helpers(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(topology_module, "_legacy_sensor_parts", _explode("topology_sensor_name_classifier"))
    monkeypatch.setattr(topology_module, "_legacy_actuator_parts", _explode("topology_actuator_name_classifier"))

    topology = build_robot_topology(
        {
            "project_name": "poison-labels",
            "goal": "rover arm drone gripper",
            "available_parts": [
                {
                    "component_id": "unknown-1",
                    "name": "servo motor camera battery rover",
                    "type": "unknown_interface",
                }
            ],
        },
        hinted_genre="generic_mechatronics",
    )

    assert topology.actuators == []
    assert topology.sensors == []
    assert topology.metadata["part_role_projection"] == "declared_structured_fields_only"


def test_model_first_impact_never_executes_keyword_domain_source_or_target_projection(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(impact_module, "_legacy_inferred_domains", _explode("impact_keyword_domains"))
    monkeypatch.setattr(impact_module, "_legacy_source_ids", _explode("impact_keyword_source_binding"))
    monkeypatch.setattr(impact_module, "_legacy_target_for_domain", _explode("impact_keyword_target_projection"))
    monkeypatch.setattr(
        impact_module,
        "interpret_impact_scope",
        lambda *args, **kwargs: parse_impact_scope_proposal(
            {
                "status": "model_proposed",
                "domains": ["firmware"],
                "reasoning": "Only firmware review is semantically proposed.",
                "confidence": 0.6,
                "unresolved_questions": [],
                "source": "model_proposed",
                "authority_effect": "none",
                "automatic_execution": False,
            }
        ),
    )

    graph = build_change_impact_graph(
        {
            "mode": "greenfield",
            "goal": "battery brownout wheel ROS motor camera arm words are adversarial only",
        }
    )

    assert graph.affected_domains == ["firmware", "system", "verification"]
    assert graph.metadata["impact_scope_source"] == "model_proposed"
    assert all(
        row.metadata["target_projection"] == "structural_domain_projection"
        for row in graph.impacts
    )


def test_model_first_physical_identity_never_executes_fuzzy_resolver_or_gap_substitution(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(
        legacy_resolver,
        "resolve_parts_to_modules_with_llm",
        _explode("legacy_fuzzy_part_resolver"),
    )
    monkeypatch.setattr(
        legacy_resolver,
        "resolve_parts_to_modules",
        _explode("legacy_regex_part_resolver"),
    )
    monkeypatch.setattr(
        legacy_resolver,
        "fill_salvage_gaps",
        _explode("legacy_magic_gap_fill"),
    )
    monkeypatch.setattr(
        legacy_resolver,
        "module_overrides_for_build",
        _explode("legacy_magic_module_override"),
    )
    monkeypatch.setattr(
        identity_truth,
        "_identity_model_enabled",
        lambda: True,
    )

    def no_match_llm(prompt: str, **kwargs: object) -> dict:
        return {
            "ok": True,
            "provider": "poison-test",
            "model": "deterministic",
            "content": json.dumps(
                {
                    "bindings": [
                        {
                            "part_index": 0,
                            "match_kind": "no_match",
                            "module_id": None,
                            "reasoning": "Generic functional resemblance is not identity.",
                        }
                    ],
                    "unresolved_questions": [],
                }
            ),
        }

    rows, meta = resolve_inventory_identity(
        [
            {
                "component_id": "fet-1",
                "name": "AO3400 generic MOSFET motor driver words",
                "type": "mosfet",
            }
        ],
        llm_callable=no_match_llm,
    )
    rows = fill_capability_gaps(rows, parts=[{"component_id": "motor-1", "type": "dc_motor"}])

    assert rows[0]["module_id"] is None
    assert meta["legacy_heuristic_used"] is False
    assert any(row.get("source") == "unresolved_capability_gap" for row in rows)
    rendered = repr(rows).lower()
    assert "l298n" not in rendered
    assert "a4988" not in rendered
    assert "mosfet-irlz44n" not in rendered
