from src.intelligence.bench_topology_capture import (
    bench_capture_to_topology_evidence,
    build_bench_capture_template,
    enrich_payload_with_bench_topology_capture,
)
from src.intelligence.hardware_plan import HardwarePlanOrchestrator
from src.intelligence.topology_evidence import topology_evidence_bridge


def _release_manifest(resource_ids):
    return {
        "release_id": "REL-BENCH-001",
        "selected_resource_ids": resource_ids,
        "released_by": "operator-1",
        "released_at": "2026-05-26T04:30:00Z",
        "scope_statement": "Release is limited to the measured bench topology capture.",
        "artifact_uris": ["session://bench/ch340c/release-report"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


def _bench_capture():
    return {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "bench-ch340c-001",
        "operator_id": "operator-1",
        "recorded_at": "2026-05-26T04:00:00Z",
        "instruments": [
            {"instrument_id": "bench_dmm_01", "instrument_type": "calibrated_dmm", "calibration_status": "valid"},
            {"instrument_id": "bench_supply_01", "instrument_type": "current_limited_supply", "calibration_status": "valid"},
            {"instrument_id": "thermal_probe_01", "instrument_type": "thermal_probe", "calibration_status": "valid"},
        ],
        "artifacts": [
            {"kind": "photo", "uri": "session://bench/ch340c/pinout-photo"},
            {"kind": "measurement_log", "uri": "session://bench/ch340c/measurement-log"},
        ],
        "connectors": [
            {
                "ref": "J1",
                "label": "bench verified CH340C UART header",
                "pins": [
                    {"pin": "1", "net": "DTR", "role": "dtr", "status": "verified"},
                    {"pin": "2", "net": "RXI", "role": "rxi", "logic_voltage": 3.3, "status": "verified"},
                    {"pin": "3", "net": "TXO", "role": "txo", "logic_voltage": 3.3, "status": "verified"},
                    {"pin": "4", "net": "VCC", "role": "vcc", "voltage": 3.3, "status": "verified"},
                    {"pin": "5", "net": "CTS", "role": "cts", "status": "verified"},
                    {"pin": "6", "net": "GND", "role": "gnd", "status": "verified"},
                ],
            }
        ],
        "measurements": [
            {
                "kind": "resistance",
                "target": "power to ground no-short",
                "value": "pass",
                "status": "pass",
                "notes": "unpowered resistance between VCC and GND is no-short",
            },
            {
                "kind": "continuity",
                "target": "connector ground to exposed ground",
                "value": "pass",
                "status": "pass",
            },
            {
                "kind": "current",
                "target": "current draw under current-limited supply",
                "value": "pass",
                "status": "pass",
                "instrument_id": "bench_supply_01",
            },
            {
                "kind": "thermal",
                "target": "thermal behavior after first power",
                "value": "normal",
                "status": "pass",
                "instrument_id": "thermal_probe_01",
            },
        ],
    }


def _public_reference_topology():
    return {
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


def test_bench_capture_converts_to_trusted_topology_and_authorizes_after_release():
    topology = bench_capture_to_topology_evidence(_bench_capture())
    bridge = topology_evidence_bridge(topology)
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "release bench verified CH340C UART harness",
            "target_authority_level": "production_repair",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "bench_topology_capture": _bench_capture(),
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["topology_j1"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 10,
                    "time_spent_minutes": 18,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "evidence_uri": "session://outcomes/topology-j1-built",
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

    assert topology["source_type"] == "bench_measurement_capture"
    assert bridge["topology_authority"]["measurement_backed"] is True
    assert bridge["topology_authority"]["trusted_measurement_count"] >= 5
    assert bridge["pin_level_splice_contracts"][0]["status"] == "ready_for_controlled_splice"
    assert plan["analysis"]["bench_topology_capture"]["actionable_topology"] is True
    assert plan["integrated_plan"]["assurance"]["can_power_or_splice"] is True
    assert plan["integrated_plan"]["production_repair_authority"]["authorized"] is True


def test_reference_template_seeds_capture_but_does_not_create_actionable_evidence():
    template = build_bench_capture_template(reference_topology=_public_reference_topology())
    enriched = enrich_payload_with_bench_topology_capture({"bench_topology_capture": template})

    assert template["connectors"][0]["reference_seed"] is True
    assert template["connectors"][0]["pins"][0]["status"] == "needs_measurement"
    assert "topology_evidence" not in enriched
    assert enriched["analysis"]["bench_topology_capture"]["actionable_topology"] is False


def test_measured_capture_replaces_public_reference_for_authority_scope():
    reference = _public_reference_topology()
    reference["connectors"].append(
        {
            "ref": "USB-C",
            "label": "USB-C connector from public schematic",
            "pins": [
                {"pin": "VBUS", "net": "VBUS", "role": "power", "voltage": 5.0},
                {"pin": "GND", "net": "GND", "role": "ground"},
                {"pin": "CC1", "net": "CC1", "role": ""},
                {"pin": "CC2", "net": "CC2", "role": ""},
            ],
        }
    )

    enriched = enrich_payload_with_bench_topology_capture(
        {
            "topology_evidence": reference,
            "bench_topology_capture": _bench_capture(),
        }
    )
    bridge = topology_evidence_bridge(enriched["topology_evidence"])

    assert enriched["reference_topology"] == reference
    assert [row["ref"] for row in enriched["topology_evidence"]["connectors"]] == ["J1"]
    assert bridge["topology_authority"]["pinout_known"] is True
    assert bridge["topology_authority"]["unknown_pin_count"] == 0


def test_visual_raspberry_pi_template_seeds_known_gpio_and_usb_pins_without_authority():
    template = build_bench_capture_template(
        board_evidence={
            "schema_version": "board_evidence.v1",
            "components": [
                {"id": "cpu", "label": "Raspberry Pi 4 Model B CPU", "kind": "processor"},
                {"id": "ram", "label": "RAM", "kind": "memory"},
            ],
            "markings": [{"id": "m1", "text": "Raspberry Pi 4 Model B"}],
            "connectors": [
                {"id": "ethernet", "label": "Ethernet Connector", "kind": "connector"},
                {"id": "gpio_header", "label": "GPIO Header", "kind": "header"},
                {"id": "usb_a_1", "label": "USB-A Port 1", "kind": "connector"},
                {"id": "usb_type_c", "label": "USB-C Power Input", "kind": "connector"},
            ],
        }
    )
    ethernet = next(row for row in template["connectors"] if row["ref"] == "ethernet")
    gpio = next(row for row in template["connectors"] if row["ref"] == "gpio_header")
    usb_a = next(row for row in template["connectors"] if row["ref"] == "usb_a_1")
    enriched = enrich_payload_with_bench_topology_capture({"bench_topology_capture": template})

    assert ethernet["pin_count"] == 8
    assert gpio["reference_seed"] is True
    assert gpio["pin_count"] == 40
    assert gpio["pins"][0]["net"] == "3V3"
    assert gpio["pins"][2]["role"] == "i2c_sda"
    assert gpio["pins"][7]["role"] == "uart_tx"
    assert gpio["pins"][18]["role"] == "spi_mosi"
    assert usb_a["pin_count"] == 4
    assert {pin["net"] for pin in usb_a["pins"]} == {"VBUS", "D-", "D+", "GND"}
    targets = {row["target"] for row in template["measurements"]}
    assert any("GPIO Header (gpio_header) supply-to-ground no-short" in target for target in targets)
    assert any("GPIO Header (gpio_header) logic voltage domain" in target for target in targets)
    assert any("USB-C Power Input (usb_type_c) USB data pair" in target for target in targets)
    assert any("Ethernet Connector (ethernet) high-speed/shield reference" in target for target in targets)
    assert not any("Ethernet Connector (ethernet) USB data pair" in target for target in targets)
    assert "topology_evidence" not in enriched
    assert enriched["analysis"]["bench_topology_capture"]["actionable_topology"] is False


def test_bench_capture_without_audit_artifact_cannot_reach_production_authority():
    capture = _bench_capture()
    capture["artifacts"] = []
    capture.pop("evidence_uri", None)
    plan = HardwarePlanOrchestrator().plan(
        {
            "goal": "release bench capture without artifacts",
            "target_authority_level": "production_repair",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "bench_topology_capture": capture,
            "outcome_history": [
                {
                    "decision": "built",
                    "selected_resource_ids_used": ["topology_j1"],
                    "measurements_recorded": True,
                    "cash_spent_usd": 0,
                    "value_recovered_usd": 10,
                    "time_spent_minutes": 18,
                    "deviations_from_plan": [],
                    "failure_or_stop_reason": "",
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "evidence_uri": "session://outcomes/topology-j1-no-bench-artifact",
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

    assert production["authorized"] is False
    assert production["measurement_provenance"]["missing_artifact_categories"]
