from src.api.v1 import main as main_module
from src.intelligence.hardware_plan import HardwarePlanOrchestrator
from src.intelligence.multiview_board_evidence import fuse_board_photo_set


def _photo_set():
    return {
        "goal": "inspect this physical board for salvage and reuse options",
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
                            {"id": "j1", "label": "USB connector", "kind": "connector", "bbox": [0.03, 0.38, 0.16, 0.52], "confidence": 0.7}
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
                            {"id": "m1", "label": "CH340C marking", "marking": "CH340C", "bbox": [0.27, 0.36, 0.38, 0.44], "confidence": 0.84}
                        ],
                        "connectors": [
                            {"id": "h1", "label": "UART header", "kind": "header", "bbox": [0.62, 0.32, 0.88, 0.44], "confidence": 0.72}
                        ],
                        "damage": [],
                    },
                },
            ]
        },
        "use_reference_catalog": False,
    }


def test_multiview_board_evidence_fuses_observations_without_fixed_view_slots():
    reconstruction = fuse_board_photo_set(_photo_set())
    evidence = reconstruction["board_evidence"]
    bridge = reconstruction["vision_evidence_bridge"]
    caps = {cap for resource in bridge["resource_candidates"] for cap in resource["capabilities"]}
    board_map = reconstruction["canonical_board_map"]
    coverage = reconstruction["capture_coverage"]

    assert reconstruction["available"] is True
    assert reconstruction["policy"]["fixed_view_slots_required"] is False
    assert reconstruction["usable_observation_count"] == 2
    assert coverage["schema_version"] == "capture_coverage.v1"
    assert coverage["required_complete"] is True
    assert coverage["score"] == 1.0
    assert "hidden_side_context" in coverage["recommended_open_lanes"]
    assert reconstruction["reconstruction_summary"]["identity_link_count"] == 1
    assert reconstruction["reconstruction_summary"]["level"] == "multi_view_reconstructed_visual_dossier"
    assert reconstruction["identity_links"][0]["type"] == "marking_resolves_component"
    assert board_map["mapped_item_count"] == 4
    assert board_map["layout_confidence"] > 0.45
    assert evidence["components"][0]["source_refs"][0]["photo_id"] == "wide_angle_1"
    assert evidence["components"][0]["identity_status"] == "marking_linked_candidate"
    assert {item["label"] for item in evidence["connectors"]} == {"UART header", "USB connector"}
    assert evidence["markings"][0]["support_count"] == 1
    assert {"usb_serial", "connector"}.issubset(caps)
    assert not any(request["request_id"] == "marking_closeups" for request in reconstruction["next_capture_requests"])


def test_multiview_capture_coverage_requests_specific_missing_observations():
    reconstruction = fuse_board_photo_set(
        {
            "board_photo_set": {
                "photo_observations": [
                    {
                        "photo_id": "connector_crop",
                        "view_hint": "connector crop",
                        "board_evidence": {
                            "schema_version": "board_evidence.v1",
                            "connectors": [
                                {"id": "j1", "label": "unlabeled header", "kind": "header", "bbox": [0.3, 0.4, 0.8, 0.48]}
                            ],
                        },
                    }
                ]
            }
        }
    )
    coverage = reconstruction["capture_coverage"]
    request_ids = {request["request_id"] for request in reconstruction["next_capture_requests"]}

    assert coverage["required_complete"] is False
    assert {"whole_board_context", "marking_identity_detail", "safety_damage_pass"}.issubset(set(coverage["open_required_lanes"]))
    assert {"whole_board_context", "marking_identity_detail", "safety_damage_pass"}.issubset(request_ids)


def test_multiview_fusion_normalizes_provider_pixel_bboxes_into_layout_map():
    reconstruction = fuse_board_photo_set(
        {
            "board_photo_set": {
                "photo_observations": [
                    {
                        "photo_id": "wide_qwen_pass",
                        "view_hint": "wide whole board qwen visual pass",
                        "provider": "qwen",
                        "parse_diagnostics": {"json_valid": True, "truncated": False},
                        "board_evidence": {
                            "schema_version": "board_evidence.v1",
                            "components": [
                                {"id": "u1", "label": "main MCU", "kind": "integrated_circuit", "bbox": [330, 280, 540, 455]},
                                {"id": "u2", "label": "power regulator", "kind": "regulator", "bbox": [112, 390, 205, 468]},
                            ],
                            "connectors": [
                                {"id": "j1", "label": "USB-C power input", "kind": "connector", "bbox": [18, 360, 126, 490]},
                                {"id": "j2", "label": "GPIO header", "kind": "header", "bbox": [650, 120, 930, 236]},
                            ],
                            "markings": [
                                {"id": "m1", "label": "STM32F103 marking", "marking": "STM32F103", "bbox": [352, 310, 506, 352]},
                            ],
                            "damage": [],
                        },
                    },
                    {
                        "photo_id": "closeup_marking_qwen_pass",
                        "view_hint": "marking closeup and connector detail",
                        "provider": "qwen",
                        "parse_diagnostics": {"json_valid": True, "truncated": False},
                        "board_evidence": {
                            "schema_version": "board_evidence.v1",
                            "components": [
                                {"id": "u1_close", "label": "main MCU", "kind": "integrated_circuit", "bbox": [210, 180, 670, 560]},
                            ],
                            "connectors": [
                                {"id": "j2_close", "label": "GPIO header", "kind": "header", "bbox": [710, 80, 990, 260]},
                            ],
                            "markings": [
                                {"id": "m1_close", "label": "STM32F103 marking", "marking": "STM32F103", "bbox": [265, 240, 545, 312]},
                            ],
                            "damage": [],
                        },
                    },
                ]
            }
        }
    )

    board_map = reconstruction["canonical_board_map"]
    statuses = {item["geometry_status"] for item in board_map["items"]}

    assert reconstruction["available"] is True
    assert board_map["mapped_item_count"] == board_map["item_count"]
    assert board_map["layout_confidence"] >= 0.70
    assert reconstruction["capture_coverage"]["required_complete"] is True
    assert "pixel_only" not in statuses
    assert any(status.startswith("provider_pixel_normalized") for status in statuses)


def test_hardware_plan_uses_multiview_fusion_as_reconstructed_board_evidence():
    plan = HardwarePlanOrchestrator().plan(_photo_set())
    analysis = plan["analysis"]
    strategy = plan["resource_strategy"]
    integrated = plan["integrated_plan"]
    closure_lanes = {lane["lane_id"]: lane for lane in analysis["active_evidence_closure_plan"]["closure_lanes"]}

    assert analysis["multiview_board_reconstruction"]["usable_observation_count"] == 2
    assert analysis["multiview_board_reconstruction"]["capture_coverage"]["required_complete"] is True
    assert analysis["board_function_inference"]["primary_function_id"] == "usb_serial_debug_bridge"
    assert analysis["arbitrary_board_trust_assessment"]["level"] == "multi_view_visual_topology_candidate"
    assert analysis["visual_topology_hypothesis"]["readiness"]["level"] == "layout_grounded_visual_topology_candidate"
    assert closure_lanes["visual_coverage"]["status"] == "complete"
    assert analysis["layout_reuse_boundaries"]["multiview_evidence"] is True
    assert set(strategy["required_capabilities"]) == {"usb_serial", "connector"}
    assert strategy["coverage"]["coverage_score"] == 1
    assert strategy["selected_resources"]
    assert integrated["status"] == "prototype_after_evidence"
    assert integrated["assurance"]["can_power_or_splice"] is False


def test_multiview_fusion_api_returns_plan_and_reconstruction_metadata():
    response = main_module.fuse_multiview_board_evidence(
        _photo_set(),
        include_hardware_plan=True,
        current_user={"user_id": "operator-1"},
    )

    assert response["metadata"]["fixed_view_slots_required"] is False
    assert response["metadata"]["user_id"] == "operator-1"
    assert response["multiview_board_reconstruction"]["available"] is True
    assert response["hardware_plan"]["analysis"]["board_function_inference"]["primary_function_id"] == "usb_serial_debug_bridge"
