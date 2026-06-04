import json
from argparse import Namespace
from pathlib import Path

from scripts.evaluate_real_board_corpus import _load_manifest, _summary, _evaluate_case
from scripts.intake_real_board_case import build_case_from_args
from src.intelligence.hardware_plan import HardwarePlanOrchestrator


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _board_evidence():
    return {
        "schema_version": "board_evidence.v1",
        "components": [
            {
                "id": "u1",
                "label": "CH340C USB serial bridge IC",
                "kind": "integrated_circuit",
                "confidence": 0.78,
            }
        ],
        "markings": [
            {
                "id": "m1",
                "label": "CH340C marking",
                "marking": "CH340C",
                "confidence": 0.84,
            }
        ],
        "connectors": [
            {"id": "j1", "label": "USB connector", "kind": "connector", "confidence": 0.74},
            {"id": "h1", "label": "UART header", "kind": "header", "confidence": 0.72},
        ],
        "damage": [],
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
            {"kind": "photo", "uri": "session://real-board/ch340c/pinout-photo"},
            {"kind": "measurement_log", "uri": "session://real-board/ch340c/measurement-log"},
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
            {"kind": "resistance", "target": "power to ground no-short", "value": "pass", "status": "pass"},
            {"kind": "continuity", "target": "connector ground to exposed ground", "value": "pass", "status": "pass"},
            {"kind": "current", "target": "current draw under current-limited supply", "value": "pass", "status": "pass", "instrument_id": "bench_supply_01"},
            {"kind": "thermal", "target": "thermal behavior after first power", "value": "normal", "status": "pass", "instrument_id": "thermal_probe_01"},
        ],
    }


def _outcome():
    return {
        "decision": "reused",
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
        "evidence_uri": "session://trial/ch340c/outcome",
    }


def _release():
    return {
        "release_id": "REAL-BOARD-CH340C-001",
        "selected_resource_ids": ["topology_j1"],
        "released_by": "operator-1",
        "approved_by": "operator-1",
        "released_at": "2026-05-26T05:00:00Z",
        "scope_statement": "Release is limited to measured CH340C UART header and loopback validation.",
        "artifact_uris": ["session://real-board/ch340c/release-report"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


def test_real_board_case_intake_writes_case_manifest_and_passes_corpus_eval(tmp_path):
    photo = tmp_path / "ch340c_front.jpg"
    photo.write_bytes(b"not a real jpeg; test only")
    evidence_path = tmp_path / "board_evidence.json"
    bench_path = tmp_path / "bench_capture.json"
    outcome_path = tmp_path / "outcome.json"
    release_path = tmp_path / "release.json"
    manifest_path = tmp_path / "manifest.local.json"
    output_root = tmp_path / "cases"
    _write_json(evidence_path, _board_evidence())
    _write_json(bench_path, _bench_capture())
    _write_json(outcome_path, _outcome())
    _write_json(release_path, _release())

    report = build_case_from_args(
        Namespace(
            case_id="real_ch340c_uart_adapter",
            title="Real CH340C UART adapter intake",
            goal="release measured CH340C UART adapter as a reusable debug harness",
            device_hint="CH340C USB serial board",
            photo=[str(photo)],
            board_evidence_json=[str(evidence_path)],
            reference_topology_json="",
            bench_capture_json=str(bench_path),
            outcome_json=str(outcome_path),
            production_release_json=str(release_path),
            required_capability=["usb_serial", "connector"],
            strategy_mode="constrained",
            target_authority_level="production_repair",
            use_reference_catalog=False,
            live_qwen=False,
            max_tokens=1024,
            output_root=output_root,
            manifest=manifest_path,
            append_manifest=True,
            force=False,
            notes="unit-test intake",
        )
    )
    manifest = _load_manifest(manifest_path)
    row = _evaluate_case(HardwarePlanOrchestrator(), manifest["cases"][0])
    summary = _summary([row], manifest)

    assert report["actual"]["production_authorized"] is True
    assert (output_root / "real_ch340c_uart_adapter" / "case.json").exists()
    assert manifest["cases"][0]["source"]["example_seed"] is False
    assert row["passed"] is True
    assert row["source_quality"]["has_board_evidence"] is True
    assert row["source_quality"]["has_topology_evidence"] is True
    assert summary["case_count"] == 1
    assert summary["example_seed_cases"] == 0
