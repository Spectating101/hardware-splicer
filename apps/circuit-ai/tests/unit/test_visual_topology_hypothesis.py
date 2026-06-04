from src.api.v1 import main as main_module
from src.intelligence.hardware_plan import HardwarePlanOrchestrator
from src.intelligence.visual_topology_hypothesis import build_visual_topology_hypothesis


def _photo_set():
    return {
        "goal": "turn this salvaged board into a safe USB serial tool if possible",
        "board_photo_set": {
            "photo_observations": [
                {
                    "photo_id": "wide_angle_1",
                    "view_hint": "wide angled board photo",
                    "provider": "qwen",
                    "parse_diagnostics": {"json_valid": True, "truncated": False},
                    "board_evidence": {
                        "schema_version": "board_evidence.v1",
                        "components": [
                            {
                                "id": "u1",
                                "label": "unknown USB bridge IC",
                                "kind": "integrated_circuit",
                                "bbox": [0.24, 0.34, 0.42, 0.52],
                                "confidence": 0.62,
                            }
                        ],
                        "connectors": [
                            {
                                "id": "j1",
                                "label": "USB connector",
                                "kind": "connector",
                                "bbox": [0.03, 0.38, 0.16, 0.52],
                                "confidence": 0.7,
                            }
                        ],
                        "damage": [],
                    },
                },
                {
                    "photo_id": "closeup_marking_1",
                    "view_hint": "closeup of IC marking and header",
                    "provider": "qwen",
                    "parse_diagnostics": {"json_valid": True, "truncated": False},
                    "board_evidence": {
                        "schema_version": "board_evidence.v1",
                        "markings": [
                            {
                                "id": "m1",
                                "label": "CH340C marking",
                                "marking": "CH340C",
                                "bbox": [0.27, 0.36, 0.38, 0.44],
                                "confidence": 0.84,
                            }
                        ],
                        "connectors": [
                            {
                                "id": "h1",
                                "label": "UART header",
                                "kind": "header",
                                "bbox": [0.62, 0.32, 0.88, 0.44],
                                "confidence": 0.72,
                            }
                        ],
                        "damage": [],
                    },
                },
            ]
        },
        "use_reference_catalog": False,
    }


def test_visual_topology_turns_multiphoto_dossier_into_measurement_queue_without_authority():
    hypothesis = build_visual_topology_hypothesis(_photo_set())
    roles = {role for row in hypothesis["connector_hypotheses"] for role in row["likely_roles"]}
    links = {row["type"] for row in hypothesis["connection_hypotheses"]}
    prompts = " ".join(task["prompt"] for task in hypothesis["measurement_queue"])
    first_anchor = hypothesis["component_anchors"][0]
    first_connector = hypothesis["connector_hypotheses"][0]
    targeted_tasks = [task for task in hypothesis["measurement_queue"] if task.get("target")]

    assert hypothesis["available"] is True
    assert hypothesis["readiness"]["level"] == "layout_grounded_visual_topology_candidate"
    assert hypothesis["readiness"]["can_power_or_splice"] is False
    assert {"usb2_connector", "uart_serial_header"}.issubset(roles)
    assert {"candidate_usb_data_path", "candidate_uart_serial_path"}.issubset(links)
    assert first_anchor["normalized_bbox"] == first_anchor["geometry"]["normalized_bbox"]
    assert first_anchor["board_zone"] == first_anchor["geometry"]["board_zone"]
    assert first_connector["normalized_bbox"] == first_connector["geometry"]["normalized_bbox"]
    assert first_connector["board_zone"] == first_connector["geometry"]["board_zone"]
    assert any(task["target"].get("normalized_bbox") for task in targeted_tasks)
    assert "topology_evidence.v1" in prompts
    assert "TX, RX, GND, and VCC" in prompts
    assert any(claim["claim"] == "pinout_known" and claim["status"] == "blocked" for claim in hypothesis["blocked_claims"])


def test_hardware_plan_uses_visual_topology_as_specific_next_measurements_not_measured_topology():
    plan = HardwarePlanOrchestrator().plan(_photo_set())
    analysis = plan["analysis"]
    trust = analysis["arbitrary_board_trust_assessment"]
    protocol_sources = {step["source"] for step in analysis["measurement_protocol"]["steps"]}

    assert analysis["visual_topology_hypothesis"]["available"] is True
    assert trust["level"] == "multi_view_visual_topology_candidate"
    assert 0.1 < trust["trust_dimensions"]["topology_confidence"] < 0.31
    assert analysis["topology_authority"] == {}
    assert plan["integrated_plan"]["assurance"]["can_power_or_splice"] is False
    assert "visual_topology_hypothesis" in protocol_sources
    assert any(task["source"] == "visual_topology_hypothesis" for task in analysis["next_evidence_tasks"])


def test_visual_topology_api_returns_candidate_only_plan():
    response = main_module.visual_topology_hypothesis(
        _photo_set(),
        include_hardware_plan=True,
        current_user={"user_id": "operator-1"},
    )

    assert response["metadata"]["candidate_only"] is True
    assert response["metadata"]["user_id"] == "operator-1"
    assert response["visual_topology_hypothesis"]["available"] is True
    assert response["hardware_plan"]["analysis"]["visual_topology_hypothesis"]["available"] is True
