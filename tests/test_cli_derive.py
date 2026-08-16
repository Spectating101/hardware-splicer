from __future__ import annotations

import json
import sys

import pytest

from hardware_splicer.cli_entry import main_derive


def _manifest(revision: str, camera: str) -> dict:
    return {
        "schema_version": "hardware_splicer.capability_manifest.v1",
        "capability_id": "vision-core",
        "revision": revision,
        "dependencies": [
            {
                "dependency_id": "component:camera:sensor_identity",
                "kind": "component_identity",
                "resolved": True,
                "value": camera,
            },
            {
                "dependency_id": "interface:wifi:config_api:v1",
                "kind": "interface_contract",
                "resolved": True,
                "value": "vision-config-v1",
            },
        ],
    }


def test_hs_derive_writes_frozen_prediction(tmp_path, monkeypatch) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    evidence = tmp_path / "evidence.json"
    output = tmp_path / "reuse-plan.json"

    baseline.write_text(json.dumps(_manifest("a", "camera-A")), encoding="utf-8")
    candidate.write_text(json.dumps(_manifest("b", "camera-B")), encoding="utf-8")
    evidence.write_text(
        json.dumps(
            [
                {
                    "evidence_id": "ev-camera",
                    "depends_on": ["component:camera:sensor_identity"],
                    "dependencies_complete": True,
                },
                {
                    "evidence_id": "ev-wifi",
                    "depends_on": ["interface:wifi:config_api:v1"],
                    "dependencies_complete": True,
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hs-derive",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--evidence",
            str(evidence),
            "--out",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main_derive()

    assert exc.value.code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "predicted"
    assert report["prediction_hash"].startswith("sha256:")
    statuses = {
        row["evidence_id"]: row["status"]
        for row in report["impact_report"]["results"]
    }
    assert statuses == {"ev-camera": "invalidated", "ev-wifi": "retained"}


def test_hs_derive_exits_nonzero_for_mismatched_capability(tmp_path, monkeypatch) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    evidence = tmp_path / "evidence.json"

    baseline.write_text(json.dumps(_manifest("a", "camera-A")), encoding="utf-8")
    wrong = _manifest("b", "camera-B")
    wrong["capability_id"] = "motion-core"
    candidate.write_text(json.dumps(wrong), encoding="utf-8")
    evidence.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hs-derive",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--evidence",
            str(evidence),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main_derive()

    assert exc.value.code == 2
