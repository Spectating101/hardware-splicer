from src.intelligence.hardware_plan import HardwarePlanOrchestrator
from src.intelligence.topology_evidence import enrich_payload_with_topology_evidence, topology_evidence_bridge


def _trusted():
    return {
        "instrument_id": "bench_dmm_01",
        "instrument_type": "calibrated_dmm",
        "calibration_status": "valid",
        "recorded_at": "2026-05-26T03:00:00Z",
        "operator_id": "operator-1",
        "evidence_uri": "session://measurements/topology",
    }


def _release_manifest(resource_ids):
    return {
        "release_id": "REL-TOPO-001",
        "selected_resource_ids": resource_ids,
        "released_by": "operator-1",
        "released_at": "2026-05-26T03:30:00Z",
        "scope_statement": "Release is limited to the measured topology_j1 low-voltage connector scope.",
        "artifact_uris": ["session://release/topology-test-report"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


def _measured_uart_topology():
    provenance = _trusted()
    return {
        "schema_version": "topology_evidence.v1",
        **provenance,
        "connectors": [
            {
                "ref": "J1",
                "label": "measured UART header",
                "status": "verified",
                "pins": [
                    {"pin": "1", "net": "GND", "role": "ground", "status": "verified"},
                    {"pin": "2", "net": "3V3", "role": "power", "voltage": 3.31, "status": "verified"},
                    {"pin": "3", "net": "UART_TX", "role": "uart_tx", "logic_voltage": 3.29, "status": "verified"},
                    {"pin": "4", "net": "UART_RX", "role": "uart_rx", "logic_voltage": 3.3, "status": "verified"},
                ],
            }
        ],
        "resistance": [
            {
                "target": "power to ground no-short",
                "value": "pass",
                "unit": "ohm",
                "notes": "unpowered resistance between power and ground is no-short",
                "status": "pass",
            }
        ],
        "current": [
            {
                "target": "current draw under current-limited supply",
                "value": "pass",
                "notes": "current draw under current-limited supply within limit",
                "status": "pass",
            }
        ],
        "thermal": [
            {
                "target": "thermal behavior after first power",
                "value": "normal",
                "notes": "temperature stable and no abnormal heat",
                "status": "pass",
            }
        ],
    }


def test_topology_evidence_bridge_creates_measured_connector_resource_and_measurements():
    bridge = topology_evidence_bridge(_measured_uart_topology())
    resource = bridge["resource_candidates"][0]
    measurement_targets = {row["target"] for row in bridge["measurement_rows"]}
    contract = bridge["pin_level_splice_contracts"][0]
    wires = {row["function"]: row for row in contract["wire_bom"]}

    assert bridge["available"] is True
    assert resource["resource_id"] == "topology_j1"
    assert resource["evidence_status"] == "measurement_backed"
    assert {"connector", "usb_serial", "power"}.issubset(set(resource["capabilities"]))
    assert bridge["topology_authority"]["pinout_known"] is True
    assert bridge["topology_authority"]["trusted_measurement_count"] >= 5
    assert "logic high voltage" in measurement_targets
    assert "power to ground no-short" in measurement_targets
    assert contract["status"] == "ready_for_controlled_splice"
    assert wires["GND"]["color"] == "black"
    assert wires["rail:3.31V"]["color"] == "red"
    assert wires["UART_TX_to_target_RX"]["to"]["endpoint"] == "target RX"
    assert wires["UART_RX_to_target_TX"]["to"]["endpoint"] == "target TX"
    assert bridge["hazard_profile"]["hazards"] == []


def test_topology_evidence_closes_splice_gates_but_still_requires_authority():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "build a USB UART debug adapter from measured board topology",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": _measured_uart_topology(),
            "repair_authority": {
                "status": "authoritative_low_risk",
                "score": 0.91,
                "required_measurements": [],
                "blocked_decisions": [],
            },
            "use_reference_catalog": False,
        }
    )

    integrated = plan["integrated_plan"]

    assert "topology_j1" in integrated["selected_resource_ids"]
    assert integrated["coverage"]["coverage_score"] == 1
    assert integrated["assurance"]["can_power_or_splice"] is True
    assert integrated["assurance"]["open_gate_count"] == 0
    assert integrated["measurement_evidence"]["closed_gate_count"] >= 5
    assert plan["analysis"]["topology_authority"]["pinout_known"] is True
    assert plan["analysis"]["machine_connection_map"]["splice_plan"]["topology_authority"]["measurement_backed"] is True
    assert integrated["execution_package"]["pin_level_splice_contracts"][0]["status"] == "ready_for_controlled_splice"
    assert integrated["execution_package"]["functional_validation_protocol"]["readiness"] == "validation_required"
    assert "Output function verified" in integrated["execution_package"]["functional_validation_protocol"]["required_before_demo"]
    assert any("UART_TX" in action for action in integrated["execution_package"]["stages"][5]["actions"])


def test_topology_evidence_can_authorize_low_voltage_production_when_outcome_is_complete():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "release measured low-voltage USB UART repair",
            "target_authority_level": "production_repair",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": _measured_uart_topology(),
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["topology_j1"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 9,
                    "time_spent_minutes": 22,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "evidence_uri": "session://outcomes/topology-j1-authority",
                }
            ],
            "production_release": _release_manifest(["topology_j1"]),
            "repair_authority": {
                "status": "authoritative_low_risk",
                "score": 0.94,
                "required_measurements": [],
                "blocked_decisions": [],
            },
            "use_reference_catalog": False,
        }
    )

    production = plan["integrated_plan"]["production_repair_authority"]

    assert plan["integrated_plan"]["completion_contract"]["workflow_done"] is True
    assert production["authorized"] is True
    assert production["decision"] == "authorized_low_voltage_repair_release"
    assert production["measurement_requirements"]["missing_categories"] == []
    assert production["measurement_provenance"]["missing_trusted_categories"] == []
    assert production["measurement_provenance"]["missing_artifact_categories"] == []
    assert production["release_manifest"]["complete"] is True
    assert plan["integrated_plan"]["execution_package"]["functional_validation_protocol"]["readiness"] == "functionally_validated"


def test_topology_evidence_short_blocks_power_and_production_authority():
    payload = {
        "goal": "reuse measured UART header with failed short check",
        "target_authority_level": "production_repair",
        "strategy_mode": "constrained",
        "required_capabilities": ["usb_serial", "connector"],
        "topology_evidence": {
            "schema_version": "topology_evidence.v1",
            **_trusted(),
            "connectors": [
                {
                    "ref": "J1",
                    "pins": [
                        {"pin": "1", "net": "GND", "role": "ground", "status": "verified"},
                        {"pin": "2", "net": "5V", "role": "power", "voltage": 5.0, "status": "verified"},
                        {"pin": "3", "net": "UART_TX", "role": "uart_tx", "logic_voltage": 3.3, "status": "verified"},
                        {"pin": "4", "net": "UART_RX", "role": "uart_rx", "logic_voltage": 3.3, "status": "verified"},
                    ],
                }
            ],
            "resistance": [
                {
                    "target": "power to ground no-short",
                    "value": "fail",
                    "notes": "short detected between 5V and GND",
                    "status": "failed",
                }
            ],
        },
        "repair_authority": {"status": "authoritative_low_risk", "score": 0.94},
        "use_reference_catalog": False,
    }

    enriched = enrich_payload_with_topology_evidence(payload)
    plan = HardwarePlanOrchestrator().plan(payload)
    hazards = enriched["hazard_profile"]["hazards"]

    assert any(hazard["hazard_id"] == "power_ground_short" for hazard in hazards)
    assert plan["integrated_plan"]["status"] == "safety_hold"
    assert plan["integrated_plan"]["assurance"]["can_power_or_splice"] is False
    assert plan["integrated_plan"]["execution_package"]["functional_validation_protocol"]["failed_count"] >= 1
    assert plan["integrated_plan"]["production_repair_authority"]["authorized"] is False


def test_public_reference_topology_seeds_pinout_but_does_not_authorize_measurement_gates():
    reference = {
        "schema_version": "topology_evidence.v1",
        "source_type": "public_reference_topology",
        "reference_uri": "https://www.sparkfun.com/sparkfun-serial-basic-breakout-ch340c-and-usb-c.html",
        "connectors": [
            {
                "ref": "J1",
                "label": "SparkFun CH340C FTDI-style header",
                "pins": [
                    {"pin": "1", "net": "DTR", "role": "dtr"},
                    {"pin": "2", "net": "RXI", "role": "rxi", "logic_voltage": 3.3},
                    {"pin": "3", "net": "TXO", "role": "txo", "logic_voltage": 3.3},
                    {"pin": "4", "net": "VCC", "role": "vcc", "voltage": 3.3},
                    {"pin": "5", "net": "CTS", "role": "cts"},
                    {"pin": "6", "net": "GND", "role": "gnd"},
                ],
            }
        ],
    }

    bridge = topology_evidence_bridge(reference)
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse public-reference SparkFun CH340C serial header",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": reference,
            "use_reference_catalog": False,
        }
    )

    assert bridge["reference_only"] is True
    assert bridge["topology_authority"]["pinout_known"] is True
    assert bridge["topology_authority"]["measurement_backed"] is False
    assert bridge["topology_authority"]["reference_backed"] is True
    assert bridge["measurement_rows"] == []
    assert bridge["pin_level_splice_contracts"] == []
    assert {"uart_tx", "uart_rx", "uart_dtr", "uart_cts"} <= {
        pin["role"] for pin in bridge["topology_evidence"]["connectors"][0]["pins"]
    }
    assert plan["analysis"]["arbitrary_board_trust_assessment"]["trust_dimensions"]["topology_confidence"] == 0.3
    assert plan["integrated_plan"]["assurance"]["can_power_or_splice"] is False
    assert any(
        "Confirm public reference topology" in gap
        for gap in plan["analysis"]["arbitrary_board_trust_assessment"]["blocking_gaps"]
    )
