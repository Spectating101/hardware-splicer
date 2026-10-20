from __future__ import annotations

import pytest

from hardware_splicer.citation_engine_bridge import record_golden_real_report


def _report(*, passed: bool = True):
    return {
        "schema_version": "hardware_splicer.splice_golden_real.v2",
        "build_id": "build-fixture-1",
        "out_dir": "/tmp/fixture",
        "report_path": "/tmp/fixture/SPLICE_GOLDEN_REAL_REPORT.json",
        "golden_capture_path": "/tmp/fixture/capture.json",
        "drc_pass": passed,
        "contract_updates_ok": passed,
        "contract_update_count": 2 if passed else 0,
        "firmware_authorized": passed,
        "authority": {"firmware_authorized": passed},
        "bench_submission_ok": passed,
        "bench_submission_error": None if passed else "fixture blocked",
        "bench_after": {
            "power_on_authorized": passed,
            "open_gate_count": 0 if passed else 1,
        },
        "simulated": False,
        "passed": passed,
    }


def test_authorized_hardware_report_records_decision_authority_and_receipt(monkeypatch):
    monkeypatch.delenv("HARDWARE_SPLICER_CITATION_ENGINE", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_CITATION_ENGINE_STORE", raising=False)

    trace = record_golden_real_report(_report(passed=True))

    assert trace["status"] == "recorded"
    assert trace["decisionRef"].startswith("hardware-splicer:decision:")
    assert trace["authorityRef"].startswith("hardware-splicer:authority:")
    assert trace["receiptRef"].startswith("hardware-splicer:receipt:")
    assert trace["bundleSchema"] == "citation-engine.bundle.v1"
    assert trace["bundleObjectCount"] >= 10


def test_blocked_hardware_report_stays_non_authorizing(monkeypatch):
    monkeypatch.delenv("HARDWARE_SPLICER_CITATION_ENGINE", raising=False)
    trace = record_golden_real_report(_report(passed=False))

    assert trace["status"] == "recorded"
    assert trace["authorityRef"] is None
    assert trace["receiptRef"].startswith("hardware-splicer:receipt:")


def test_bridge_rejects_report_whose_declared_pass_conflicts_with_evidence(monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_CITATION_ENGINE_STRICT", "1")
    inconsistent = _report(passed=True)
    inconsistent["bench_submission_ok"] = False

    with pytest.raises(ValueError, match="report.passed conflicts"):
        record_golden_real_report(inconsistent)


def test_bridge_kill_switch_is_independent(monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_CITATION_ENGINE", "off")
    trace = record_golden_real_report(_report(passed=True))
    assert trace == {"enabled": False, "status": "disabled"}


def test_jsonl_store_is_idempotent_for_same_hardware_report(monkeypatch, tmp_path):
    store_path = tmp_path / "hardware-citation-engine.jsonl"
    monkeypatch.setenv("HARDWARE_SPLICER_CITATION_ENGINE_STORE", str(store_path))
    monkeypatch.delenv("HARDWARE_SPLICER_CITATION_ENGINE", raising=False)

    first = record_golden_real_report(_report(passed=True))
    second = record_golden_real_report(_report(passed=True))

    assert first["decisionDigest"] == second["decisionDigest"]
    assert first["receiptDigest"] == second["receiptDigest"]
    assert first["bundleFingerprint"] == second["bundleFingerprint"]
    assert store_path.exists()
