from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.hardware_plan import HardwarePlanOrchestrator


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
        "release_id": "REL-AUTH-001",
        "selected_resource_ids": resource_ids,
        "released_by": "operator-1",
        "released_at": "2026-05-26T03:30:00Z",
        "scope_statement": "Release is limited to the measured topology_j1 low-voltage connector scope.",
        "artifact_uris": ["session://release/authority-test-report"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


def _visual_board_evidence():
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {
                "id": "u1",
                "label": "CH340C USB serial bridge IC",
                "kind": "integrated_circuit",
                "confidence": 0.78,
            },
            {
                "id": "j1",
                "label": "USB connector",
                "kind": "connector",
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


def _shorted_uart_topology():
    return {
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
    }


def test_visual_only_board_evidence_derives_candidate_authority_not_power_authority():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse a photographed USB UART board",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "board_evidence": _visual_board_evidence(),
            "use_reference_catalog": False,
        }
    )

    authority = plan["integrated_plan"]["authority"]
    repair_authority = plan["analysis"]["repair_authority"]
    trust = plan["analysis"]["evidence_trust"]
    lanes = {lane["lane_id"]: lane for lane in repair_authority["authority_lanes"]}

    assert repair_authority["status"] == "visual_only"
    assert authority["repair_authority_status"] == "visual_only"
    assert authority["release_authorized"] is False
    assert plan["integrated_plan"]["assurance"]["can_power_or_splice"] is False
    assert repair_authority["authority_state"]["power_or_splice"] == "blocked_until_topology_and_measurements"
    assert lanes["measured_pinout"]["status"] == "warn"
    assert lanes["no_short"]["status"] == "warn"
    assert any(step["lane_id"] == "measured_pinout" for step in repair_authority["unlock_plan"])
    assert any("topology" in item.lower() for item in repair_authority["required_measurements"])
    assert any("image-only evidence" in blocker.lower() for blocker in trust["blockers"])
    assert "first power or physical splice" in repair_authority["blocked_decisions"]


def test_measured_trusted_topology_derives_authority_and_production_release_without_manual_authority():
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
            "use_reference_catalog": False,
        }
    )

    integrated = plan["integrated_plan"]
    production = integrated["production_repair_authority"]
    repair_authority = plan["analysis"]["repair_authority"]
    lanes = {lane["lane_id"]: lane for lane in repair_authority["authority_lanes"]}

    assert repair_authority["status"] == "authoritative_low_risk"
    assert repair_authority["required_measurements"] == []
    assert lanes["no_short"]["status"] == "pass"
    assert lanes["reference_continuity"]["status"] == "pass"
    assert lanes["voltage_domain"]["status"] == "pass"
    assert lanes["current_limit"]["status"] == "pass"
    assert lanes["thermal_behavior"]["status"] == "pass"
    assert lanes["logic_interface"]["status"] == "pass"
    assert lanes["terminal_outcome"]["status"] == "pass"
    assert repair_authority["authority_state"]["production_release"] == "candidate_ready"
    assert integrated["authority"]["repair_authority_status"] == "authoritative_low_risk"
    assert integrated["authority"]["release_authorized"] is True
    assert integrated["assurance"]["can_power_or_splice"] is True
    assert production["authorized"] is True
    assert production["decision"] == "authorized_low_voltage_repair_release"
    assert production["release_manifest"]["complete"] is True


def test_failed_short_topology_derives_blocked_authority_even_without_manual_authority():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse measured UART header with failed short check",
            "target_authority_level": "production_repair",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": _shorted_uart_topology(),
            "use_reference_catalog": False,
        }
    )

    repair_authority = plan["analysis"]["repair_authority"]
    trust = plan["analysis"]["evidence_trust"]
    integrated = plan["integrated_plan"]
    lanes = {lane["lane_id"]: lane for lane in repair_authority["authority_lanes"]}

    assert repair_authority["status"] == "blocked"
    assert repair_authority["authority_state"]["power_or_splice"] == "blocked"
    assert lanes["hazard_scope"]["status"] == "fail"
    assert lanes["no_short"]["status"] == "fail"
    assert any("short" in blocker.lower() for blocker in trust["blockers"])
    assert integrated["status"] == "safety_hold"
    assert integrated["assurance"]["can_power_or_splice"] is False
    assert integrated["production_repair_authority"]["authorized"] is False


def test_measured_hard_blockers_override_supplied_authority_packet():
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "reuse measured UART header with bad manual authority",
            "target_authority_level": "production_repair",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": _shorted_uart_topology(),
            "repair_authority": {
                "status": "authoritative_low_risk",
                "score": 0.96,
                "required_measurements": [],
                "blocked_decisions": [],
                "source": "operator_or_llm_claim",
            },
            "use_reference_catalog": False,
        }
    )

    analysis = plan["analysis"]
    integrity = analysis["authority_integrity"]
    integrated = plan["integrated_plan"]

    assert analysis["operator_repair_authority"]["status"] == "authoritative_low_risk"
    assert analysis["repair_authority"]["status"] == "blocked"
    assert analysis["repair_authority"]["source"] == "evidence_safety_override"
    assert integrity["overrode_supplied_authority"] is True
    assert integrity["hard_blocked_by_evidence"] is True
    assert any("No-short" in blocker for blocker in integrity["hard_blockers"])
    assert integrated["authority"]["repair_authority_status"] == "blocked"
    assert integrated["authority"]["release_authorized"] is False
    assert integrated["status"] == "safety_hold"


def test_board_session_intake_derives_authority_without_stale_measurement_tasks(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")

    session = store.create_session(
        {
            "description": "measured UART board",
            "route": "repair",
            "topology_evidence": _measured_uart_topology(),
        },
        user_id="operator-1",
    )

    analysis = session["analyses"][0]["results"]
    open_sources = {
        task["source"]
        for task in session["evidence_tasks"]
        if task.get("status", "open") == "open"
    }

    assert analysis["repair_authority"]["status"] == "authoritative_low_risk"
    assert analysis["evidence_trust"]["launch_readiness"] == "experimental_mvp_authority_ready"
    assert "repair_authority_gate" not in open_sources
    assert "evidence_trust_gate" not in open_sources
    assert "splice_measurement_gate" not in open_sources
