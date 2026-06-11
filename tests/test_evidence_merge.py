from __future__ import annotations

from hardware_splicer.evidence_extractor import _merge_evidence


def test_merge_evidence_prefers_verified_over_observed():
    target = {
        "mechanical_measurement_capture": {
            "dimensions": [
                {"target": "pump_mount width", "value_mm": 55.0, "status": "verified"},
            ]
        }
    }
    patch = {
        "mechanical_measurement_capture": {
            "dimensions": [
                {"target": "pump_mount width", "value_mm": 54.0, "status": "observed"},
            ]
        }
    }
    _merge_evidence(target, patch)
    row = target["mechanical_measurement_capture"]["dimensions"][0]
    assert row["status"] == "verified"
    assert row["value_mm"] == 55.0


def test_merge_evidence_upgrades_status_when_patch_is_stronger():
    target = {
        "mechanical_measurement_capture": {
            "dimensions": [
                {"target": "controller_case inner width", "value_mm": 90.0, "status": "observed"},
            ]
        }
    }
    patch = {
        "mechanical_measurement_capture": {
            "dimensions": [
                {"target": "controller_case inner width", "value_mm": 95.0, "status": "verified"},
            ]
        }
    }
    _merge_evidence(target, patch)
    row = target["mechanical_measurement_capture"]["dimensions"][0]
    assert row["status"] == "verified"
    assert row["value_mm"] == 95.0
