from __future__ import annotations

import hardware_splicer.integrations.llm_policy as llm_policy
import hardware_splicer.module_resolution_truth as truth_module
import hardware_splicer.salvage_bridge as bridge


def test_legacy_splice_plan_architecture_and_synthetic_blocks_are_quarantined() -> None:
    sanitized, audit = bridge._sanitize_legacy_splice_plan(
        {
            "target": {"recommended_build_id": "automatic_plant_watering"},
            "reusable_blocks": [
                {
                    "block_id": "synthetic-driver",
                    "function_type": "actuator_driver",
                    "module_id": "l298n",
                }
            ],
            "verdict": "candidate",
        },
        offline=False,
    )
    assert sanitized["target"].get("recommended_build_id") is None
    assert sanitized["target"]["legacy_recommended_build_id_ignored"] == "automatic_plant_watering"
    assert sanitized["reusable_blocks"] == []
    assert sanitized["legacy_reusable_blocks_ignored"][0]["module_id"] == "l298n"
    assert sanitized["architecture_authority"] == "ignored_legacy_heuristic"
    assert audit["legacy_reusable_block_count"] == 1


def test_model_first_salvage_package_preserves_unknown_donor_identity(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(truth_module, "_identity_model_enabled", lambda: False)

    bridge.ensure_circuit_import_path()
    import src.intelligence.diy_project_engineer as diy_engineer
    from src.intelligence.salvage_splice_planner import SalvageSplicePlanner
    import hardware_splicer.integrations.qwen_workshop_review as workshop
    import hardware_splicer.evidence_salvage_bridge as evidence_bridge

    monkeypatch.setattr(
        SalvageSplicePlanner,
        "plan",
        lambda self, payload: {
            "target": {"recommended_build_id": "automatic_plant_watering"},
            "reusable_blocks": [
                {
                    "block_id": "synthetic-l298n",
                    "name": "planner synthetic driver",
                    "function_type": "actuator_driver",
                    "module_id": "l298n",
                    "capabilities": ["motor_drive"],
                }
            ],
            "verdict": "candidate",
            "confidence": 0.8,
        },
    )
    monkeypatch.setattr(
        diy_engineer,
        "build_diy_project_engineering_plan",
        lambda payload: {
            "project_intent": {"mapped_build_id": "robot_drive_base"},
            "resource_plan": {"strategy_mode": "constrained"},
        },
    )
    monkeypatch.setattr(
        bridge,
        "_pick_build_decision",
        lambda *args, **kwargs: {
            "build_id": None,
            "source": "unresolved",
            "confidence": 0.0,
            "authority_effect": "none",
            "legacy_fallback_used": False,
            "reasoning": "No defensible bounded architecture.",
            "unresolved_questions": ["Resolve architecture."],
            "legacy_planner_ids_ignored": {
                "keyword": None,
                "diy": "robot_drive_base",
                "splice": "automatic_plant_watering",
            },
        },
    )
    monkeypatch.setattr(workshop, "workshop_review_enabled", lambda: False)
    monkeypatch.setattr(
        bridge,
        "merge_goal_modules_with_inventory",
        lambda goal, resolved, constrained=False: list(resolved),
    )
    monkeypatch.setattr(bridge, "should_use_scratch_compose", lambda **kwargs: True)
    monkeypatch.setattr(
        bridge,
        "salvage_plan_input_from_intake",
        lambda splice_plan, **kwargs: {
            "target": dict(splice_plan.get("target") or {}),
            "resolved_modules": list(kwargs.get("resolved_modules") or []),
        },
    )
    monkeypatch.setattr(bridge, "build_bringup_card", lambda **kwargs: {"status": "candidate"})
    monkeypatch.setattr(bridge, "analyze_salvage_gaps", lambda **kwargs: {"status": "candidate"})
    monkeypatch.setattr(bridge, "build_salvage_bom_estimate", lambda **kwargs: {"items": []})
    monkeypatch.setattr(bridge, "generate_firmware_from_salvage", lambda **kwargs: {"status": "planned"})
    monkeypatch.setattr(
        bridge,
        "build_mecha_project_spec",
        lambda **kwargs: {"kind": "generic", "project_spec": {}},
    )
    monkeypatch.setattr(
        evidence_bridge,
        "attach_evidence_first_integrations",
        lambda package: package,
    )

    package = bridge.build_intake_salvage_package(
        goal="Use the donor capability without guessing its identity.",
        parts=[
            {
                "component_id": "motor-1",
                "name": "generic DC motor",
                "type": "dc_motor",
            }
        ],
        constraints={
            "strategy_mode": "constrained",
            "power_topology": "usb_5v",
        },
        donor_context={
            "reusable_blocks": [
                {
                    "block_id": "real-donor-driver",
                    "name": "unknown donor H-bridge",
                    "function_type": "actuator_driver",
                    "capabilities": ["bidirectional_dc_motor_drive"],
                    "status": "reusable",
                }
            ]
        },
    )

    assert package["recommended_build_id"] is None
    assert package["legacy_planner_architecture_authority"] == "ignored"
    assert package["splice_plan"]["target"].get("recommended_build_id") is None
    assert package["splice_plan"]["reusable_blocks"] == []
    assert package["legacy_planner_context"]["legacy_recommended_build_id"] == "automatic_plant_watering"
    assert package["legacy_planner_context"]["diy_mapped_build_id"] == "robot_drive_base"
    assert package["power_topology"] == "usb_5v"
    assert package["module_overrides"].get("pwr") is None

    donor = next(
        row
        for row in package["resolved_modules"]
        if row.get("donor_block_id") == "real-donor-driver"
    )
    assert donor["module_id"] is None
    assert donor["role"] == "drv"
    assert donor["external_capability_only"] is True

    physical = next(
        row
        for row in package["resolved_modules"]
        if row.get("instance_id") == "motor-1"
    )
    assert physical["module_id"] is None
    assert physical["identity_status"] == "unresolved"

    canonical_text = repr(
        {
            "resolved_modules": package["resolved_modules"],
            "module_overrides": package["module_overrides"],
            "recommended_build_id": package["recommended_build_id"],
            "graph_input": package["graph_input"],
        }
    ).lower()
    assert "l298n" not in canonical_text
    assert "a4988" not in canonical_text
    assert "mosfet-irlz44n" not in canonical_text


def test_model_first_workshop_review_is_advisory_only(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(truth_module, "_identity_model_enabled", lambda: False)

    bridge.ensure_circuit_import_path()
    import src.intelligence.diy_project_engineer as diy_engineer
    from src.intelligence.salvage_splice_planner import SalvageSplicePlanner
    import hardware_splicer.integrations.qwen_workshop_review as workshop
    import hardware_splicer.evidence_salvage_bridge as evidence_bridge

    monkeypatch.setattr(
        SalvageSplicePlanner,
        "plan",
        lambda self, payload: {"target": {}, "reusable_blocks": [], "verdict": "candidate", "confidence": 0.5},
    )
    monkeypatch.setattr(
        diy_engineer,
        "build_diy_project_engineering_plan",
        lambda payload: {"project_intent": {}, "resource_plan": {"strategy_mode": "constrained"}},
    )
    monkeypatch.setattr(
        bridge,
        "_pick_build_decision",
        lambda *args, **kwargs: {
            "build_id": None,
            "source": "unresolved",
            "confidence": 0.0,
            "authority_effect": "none",
            "legacy_fallback_used": False,
            "reasoning": "Unresolved.",
            "unresolved_questions": [],
            "legacy_planner_ids_ignored": {},
        },
    )
    monkeypatch.setattr(workshop, "workshop_review_enabled", lambda: True)
    monkeypatch.setattr(
        workshop,
        "call_qwen_workshop_review",
        lambda **kwargs: {
            "ok": True,
            "role_overrides": {"drv": "mosfet-irlz44n"},
            "add_modules": [{"module_id": "mosfet-irlz44n", "role": "drv"}],
            "suggested_build_id": "automatic_plant_watering",
            "confidence": 0.9,
        },
    )
    monkeypatch.setattr(
        bridge,
        "merge_goal_modules_with_inventory",
        lambda goal, resolved, constrained=False: list(resolved),
    )
    monkeypatch.setattr(bridge, "should_use_scratch_compose", lambda **kwargs: True)
    monkeypatch.setattr(bridge, "salvage_plan_input_from_intake", lambda splice_plan, **kwargs: {})
    monkeypatch.setattr(bridge, "build_bringup_card", lambda **kwargs: {})
    monkeypatch.setattr(bridge, "analyze_salvage_gaps", lambda **kwargs: {})
    monkeypatch.setattr(bridge, "build_salvage_bom_estimate", lambda **kwargs: {})
    monkeypatch.setattr(bridge, "generate_firmware_from_salvage", lambda **kwargs: {})
    monkeypatch.setattr(bridge, "build_mecha_project_spec", lambda **kwargs: {"kind": "generic", "project_spec": {}})
    monkeypatch.setattr(evidence_bridge, "attach_evidence_first_integrations", lambda package: package)

    package = bridge.build_intake_salvage_package(
        goal="Keep unknown inventory unknown.",
        parts=[{"component_id": "fet-1", "name": "AO3400 MOSFET", "type": "mosfet"}],
        constraints={"strategy_mode": "constrained"},
    )

    assert package["recommended_build_id"] is None
    assert all(row.get("module_id") != "mosfet-irlz44n" for row in package["resolved_modules"])
    review = package["salvage_resolution"]["workshop_review"]
    assert review["application_status"] == "advisory_only_model_first"
    assert review["physical_identity_mutated"] is False
    assert review["architecture_mutated"] is False
