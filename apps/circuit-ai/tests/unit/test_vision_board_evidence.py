from src.intelligence.hardware_plan import HardwarePlanOrchestrator
from src.intelligence.vision_board_evidence import board_evidence_bridge, enrich_payload_with_board_evidence


def _qwen_board_evidence():
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {
                "id": "u1",
                "label": "CH340C USB serial bridge IC",
                "kind": "integrated_circuit",
                "bbox": [0.2, 0.2, 0.35, 0.35],
                "confidence": 0.78,
            },
            {
                "id": "j1",
                "label": "USB connector",
                "kind": "connector",
                "bbox": [0.05, 0.4, 0.18, 0.52],
                "confidence": 0.74,
            },
        ],
        "connectors": [
            {
                "id": "h1",
                "label": "UART header",
                "kind": "header",
                "confidence": 0.7,
                "missing_evidence": ["confirm pinout before connecting target"],
            }
        ],
        "damage": [],
        "markings": [],
        "regions": [],
        "test_points": [],
        "salvage_candidates": [],
    }


def test_qwen_board_evidence_bridge_creates_candidate_resources_and_gates():
    bridge = board_evidence_bridge(_qwen_board_evidence())
    resources = bridge["resource_candidates"]
    ch340 = [resource for resource in resources if resource["resource_id"] == "vision_u1"][0]
    header = [resource for resource in resources if resource["resource_id"] == "vision_h1"][0]

    assert bridge["available"] is True
    assert ch340["resource_kind"] == "salvaged"
    assert "usb_serial" in ch340["capabilities"]
    assert "connector" in ch340["capabilities"]
    assert ch340["evidence_status"] == "needs_evidence"
    assert any("UART voltage level" in gate for gate in ch340["required_tests"])
    assert any("pinout" in gate.lower() for gate in header["required_tests"])
    assert bridge["policy"]["vision_evidence_is_candidate_only"] is True


def test_connector_like_components_are_promoted_to_connectors():
    bridge = board_evidence_bridge(
        {
            "schema_version": "board_evidence.v1",
            "components": [
                {"id": "cpu", "label": "CPU", "kind": "integrated_circuit", "confidence": 0.9},
                {"id": "gpio", "label": "40-pin GPIO header", "kind": "connector", "confidence": 0.88},
                {"id": "usb_c", "label": "USB-C power input", "kind": "component", "confidence": 0.87},
            ],
            "connectors": [],
        }
    )

    evidence = bridge["board_evidence"]
    resources = bridge["resource_candidates"]

    assert [item["id"] for item in evidence["components"]] == ["cpu"]
    assert {item["id"] for item in evidence["connectors"]} == {"gpio", "usb_c"}
    assert any(resource["resource_id"] == "vision_gpio" and "connector" in resource["capabilities"] for resource in resources)


def test_single_board_computer_connectors_and_compute_caps_are_preserved():
    bridge = board_evidence_bridge(
        {
            "schema_version": "board_evidence.v1",
            "components": [
                {"id": "cpu", "label": "CPU / SoC", "kind": "processor", "confidence": 0.74},
                {"id": "ram", "label": "RAM package", "kind": "memory", "confidence": 0.7},
            ],
            "markings": [{"id": "m1", "text": "Raspberry Pi 4 Model B"}],
            "connectors": [
                {"id": "usb_c", "label": "USB-C power input", "kind": "connector"},
                {"id": "eth", "label": "Ethernet connector", "kind": "connector"},
                {"id": "hdmi", "label": "HDMI connector", "kind": "connector"},
                {"id": "gpio", "label": "40-pin GPIO header", "kind": "header"},
            ],
        }
    )

    caps = {cap for resource in bridge["resource_candidates"] for cap in resource["capabilities"]}

    assert bridge["board_evidence"]["markings"][0]["label"] == "Raspberry Pi 4 Model B"
    assert bridge["board_evidence"]["markings"][0]["text"] == "Raspberry Pi 4 Model B"
    assert {"controller", "power", "connector", "network_interface", "display_or_ui"}.issubset(caps)


def test_marking_only_board_evidence_creates_groundable_resource_candidate():
    bridge = board_evidence_bridge(
        {
            "schema_version": "board_evidence.v1",
            "components": [{"id": "u1", "label": "unknown regulator package", "kind": "integrated_circuit"}],
            "markings": [{"id": "m1", "label": "AMS1117-3.3", "marking": "AMS1117-3.3", "confidence": 0.76}],
            "connectors": [{"id": "j1", "label": "VIN GND VOUT header", "kind": "header"}],
        }
    )

    marking_resources = [resource for resource in bridge["resource_candidates"] if resource["resource_id"] == "vision_m1"]

    assert marking_resources
    assert "power" in marking_resources[0]["capabilities"]
    assert marking_resources[0]["evidence_status"] == "needs_evidence"


def test_rs485_marking_creates_network_interface_candidate():
    bridge = board_evidence_bridge(
        {
            "schema_version": "board_evidence.v1",
            "components": [{"id": "u1", "label": "MAX485 transceiver", "kind": "integrated_circuit"}],
            "markings": [{"id": "m1", "label": "MAX485", "marking": "MAX485", "confidence": 0.76}],
            "connectors": [{"id": "j1", "label": "A B VCC GND header", "kind": "header"}],
        }
    )

    resources = bridge["resource_candidates"]
    caps = {cap for resource in resources for cap in resource["capabilities"]}

    assert "network_interface" in caps
    assert "connector" in caps


def test_qwen_board_evidence_enriches_hardware_plan_without_authorizing_reuse():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "build a USB UART debug adapter from the photographed board",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "board_evidence": _qwen_board_evidence(),
            "use_reference_catalog": False,
        }
    )

    strategy = plan["resource_strategy"]
    selected_ids = {resource["resource_id"] for resource in strategy["selected_resources"]}
    enriched_ids = {
        resource["resource_id"]
        for resource in enrich_payload_with_board_evidence({"board_evidence": _qwen_board_evidence()})["available_resources"]
    }
    integrated = plan["integrated_plan"]

    assert "vision_u1" in selected_ids
    assert "vision_h1" in enriched_ids
    assert strategy["coverage"]["coverage_score"] == 1
    assert integrated["assurance"]["can_power_or_splice"] is False
    assert any("logic voltage" in action for action in integrated["next_actions"])
    assert plan["analysis"]["machine_connection_map"]["splice_plan"]


def test_qwen_board_evidence_hazard_candidates_block_production_authority():
    enriched = enrich_payload_with_board_evidence(
        {
            "goal": "reuse a battery board",
            "target_authority_level": "production_repair",
            "board_evidence": {
                "schema_version": "board_evidence.v1",
                "components": [
                    {
                        "id": "bat1",
                        "label": "swollen lithium battery pack",
                        "kind": "battery_pack",
                        "confidence": 0.82,
                    }
                ],
                "damage": [
                    {
                        "id": "d1",
                        "label": "swollen lithium pouch cell",
                        "severity": "critical",
                        "confidence": 0.78,
                    }
                ],
            },
            "use_reference_catalog": False,
        }
    )

    hazards = enriched["hazard_profile"]["hazards"]

    assert any(hazard["hazard_id"] == "damaged_lithium_pack" for hazard in hazards)
    assert enriched["hazard_profile"]["energy_domain"] == "battery_candidate"
    assert enriched["vision_evidence_bridge"]["policy"]["hazards_cannot_be_cleared_by_vision_text"] is True
