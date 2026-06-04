from src.intelligence.active_evidence_closure import build_active_evidence_closure_plan
from src.intelligence.hardware_plan import HardwarePlanOrchestrator


def _raspberry_pi_board_evidence():
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {"id": "cpu", "label": "Raspberry Pi 4 Model B CPU", "kind": "processor", "confidence": 0.76},
            {"id": "ram", "label": "RAM", "kind": "memory", "confidence": 0.7},
        ],
        "markings": [{"id": "m1", "text": "Raspberry Pi 4 Model B", "confidence": 0.82}],
        "connectors": [
            {"id": "gpio_header", "label": "GPIO Header", "kind": "header", "confidence": 0.76},
            {"id": "usb_type_c", "label": "USB-C Power Input", "kind": "connector", "confidence": 0.73},
            {"id": "ethernet", "label": "Ethernet Connector", "kind": "connector", "confidence": 0.72},
        ],
        "damage": [],
    }


def test_active_evidence_closure_builds_investigation_campaign_from_visual_board():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse this Raspberry Pi board as an embedded controller",
            "device_hint": "Raspberry Pi single-board computer",
            "board_evidence": _raspberry_pi_board_evidence(),
            "required_capabilities": ["controller", "connector", "power"],
            "strategy_mode": "constrained",
        }
    )
    closure = plan["analysis"]["active_evidence_closure_plan"]
    targets = {task["prompt"] for task in closure["next_best_tasks"]}

    assert closure["schema_version"] == "active_evidence_closure_plan.v1"
    assert closure["available"] is True
    assert closure["current_stage"] == "active_topology_closure"
    assert closure["evidence_state"]["bench_template_connector_count"] >= 3
    assert closure["bench_capture_template_preview"]["measurement_count"] >= 10
    assert any("GPIO Header" in prompt and "logic domain" in prompt for prompt in targets)
    assert any("USB-C Power Input" in prompt and "pin count" in prompt for prompt in targets)
    assert any(item["claim"] in {"pinout_known", "safe_power_or_splice", "production_or_splice_authority"} for item in closure["cannot_claim_yet"])
    assert plan["integrated_plan"]["production_repair_authority"]["authorized"] is False


def test_active_evidence_closure_recognizes_complete_release_state_from_trust_packet():
    closure = build_active_evidence_closure_plan(
        {},
        analysis={
            "arbitrary_board_trust_assessment": {
                "level": "production_release_candidate",
                "score": 0.93,
                "production_readiness_score": 0.96,
                "trust_dimensions": {
                    "visual_coverage": 0.9,
                    "part_grounding": 0.9,
                    "topology_confidence": 0.9,
                    "evidence_independence": 0.9,
                },
                "measurement_provenance": {
                    "trusted_categories": ["resistance", "continuity", "voltage", "current", "thermal"],
                    "missing_trusted_categories": [],
                    "trusted_measurement_count": 8,
                },
                "functional_outcome": {"available": True, "terminal_success": True, "missing_requirements": []},
                "release_package": {"available": True, "complete": True, "missing_requirements": []},
                "blocking_gaps": [],
            },
            "topology_authority": {
                "measurement_backed": True,
                "pinout_known": True,
                "shorts_detected": False,
                "trusted_measurement_count": 8,
            },
            "bench_protocol_pack": {
                "schema_version": "bench_protocol_pack.v1",
                "step_count": 5,
                "title": "USB/UART debug bridge reuse",
                "required_measurement_categories": ["resistance", "continuity", "voltage", "current", "thermal", "logic"],
            },
        },
    )

    assert closure["current_stage"] == "release_closure"
    assert closure["authority_ceiling_if_next_batch_closes"] == 1.0
    assert "measured connector topology for captured scope" in closure["can_claim_now"]
    assert all(lane["status"] == "complete" for lane in closure["closure_lanes"][-3:])


def test_active_evidence_closure_keeps_outcome_lane_open_for_incomplete_outcome_contract():
    closure = build_active_evidence_closure_plan(
        {
            "outcome_history": [
                {
                    "decision": "reused",
                    "selected_resource_ids_used": ["topology_j1"],
                    "measurements_recorded": True,
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "evidence_uri": "session://bench/ch340c/outcome",
                }
            ],
            "production_release": {
                "release_id": "REL-CH340C-001",
                "selected_resource_ids": ["topology_j1"],
                "released_by": "operator-1",
                "released_at": "2026-05-26T05:00:00Z",
                "scope_statement": "Release is limited to measured CH340C UART header.",
                "artifact_uris": ["session://bench/ch340c/release"],
                "acceptance_reviewed": True,
                "repeatability_count": 1,
            },
        },
        analysis={
            "arbitrary_board_trust_assessment": {
                "level": "production_release_candidate",
                "score": 0.91,
                "production_readiness_score": 0.94,
                "measurement_provenance": {
                    "trusted_categories": ["resistance", "continuity", "voltage", "current", "thermal"],
                    "missing_trusted_categories": [],
                    "trusted_measurement_count": 8,
                },
                "functional_outcome": {"available": True, "terminal_success": True, "missing_requirements": []},
                "release_package": {"available": True, "complete": True, "missing_requirements": []},
                "blocking_gaps": [],
            },
            "topology_authority": {
                "measurement_backed": True,
                "pinout_known": True,
                "shorts_detected": False,
                "trusted_measurement_count": 8,
            },
        },
    )

    lanes = {lane["lane_id"]: lane for lane in closure["closure_lanes"]}

    assert closure["current_stage"] == "release_packaging"
    assert lanes["terminal_outcome"]["status"] == "open"
    assert closure["evidence_state"]["missing_outcome_contract_fields"] == [
        "cash_spent_usd",
        "value_recovered_usd",
        "time_spent_minutes",
        "deviations_from_plan",
    ]
    assert any("Complete outcome fields" in task["prompt"] for task in lanes["terminal_outcome"]["tasks"])
