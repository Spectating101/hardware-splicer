from __future__ import annotations

from hardware_splicer.capability_manifest import diff_capability_manifests
from hardware_splicer.evidence_impact import evaluate_evidence_impact


def _manifest(revision: str, camera: str, camera_config: str) -> dict:
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
                "dependency_id": "interface:camera:sensor_configuration",
                "kind": "interface_contract",
                "resolved": True,
                "value": camera_config,
            },
            {
                "dependency_id": "interface:wifi:config_api:v1",
                "kind": "interface_contract",
                "resolved": True,
                "value": {"transport": "wifi", "api": "vision-config-v1"},
            },
            {
                "dependency_id": "mechanical:base:mount_pattern:v1",
                "kind": "mechanical_contract",
                "resolved": True,
                "value": {"pattern": "vision-base-v1"},
            },
        ],
    }


def _evidence_rows() -> list[dict]:
    return [
        {
            "evidence_id": "ev-camera-identity",
            "depends_on": ["component:camera:sensor_identity"],
            "dependencies_complete": True,
        },
        {
            "evidence_id": "ev-camera-driver-config",
            "depends_on": [
                "ev-camera-identity",
                "interface:camera:sensor_configuration",
            ],
            "dependencies_complete": True,
        },
        {
            "evidence_id": "ev-optical-benchmark",
            "depends_on": ["ev-camera-driver-config", "condition:lighting:baseline"],
            "dependencies_complete": True,
        },
        {
            "evidence_id": "ev-wifi-api-contract",
            "depends_on": ["interface:wifi:config_api:v1"],
            "dependencies_complete": True,
        },
        {
            "evidence_id": "ev-enclosure-base",
            "depends_on": ["mechanical:base:mount_pattern:v1"],
            "dependencies_complete": True,
        },
    ]


def test_camera_manifest_change_produces_selective_change_set() -> None:
    baseline = _manifest("vision-a-r1", "camera-A", "camera-A-config")
    candidate = _manifest("vision-b-r1", "camera-B", "camera-B-config")

    diff = diff_capability_manifests(baseline, candidate)

    assert diff["status"] == "evaluated"
    assert diff["changed_dependency_ids"] == [
        "component:camera:sensor_identity",
        "interface:camera:sensor_configuration",
    ]
    assert diff["unchanged_dependency_ids"] == [
        "interface:wifi:config_api:v1",
        "mechanical:base:mount_pattern:v1",
    ]
    assert diff["metadata"]["semantic_equivalence_inferred"] is False


def test_manifest_diff_drives_selective_evidence_invalidation() -> None:
    baseline = _manifest("vision-a-r1", "camera-A", "camera-A-config")
    candidate = _manifest("vision-b-r1", "camera-B", "camera-B-config")
    diff = diff_capability_manifests(baseline, candidate)

    report = evaluate_evidence_impact(
        {
            "schema_version": "hardware_splicer.evidence_impact_case.v1",
            "changed_dependency_ids": diff["changed_dependency_ids"],
            "unresolved_dependency_ids": diff["unresolved_dependency_ids"],
            "evidence_items": _evidence_rows(),
        }
    )
    statuses = {row["evidence_id"]: row["status"] for row in report["results"]}

    assert statuses["ev-camera-identity"] == "invalidated"
    assert statuses["ev-camera-driver-config"] == "invalidated"
    assert statuses["ev-optical-benchmark"] == "invalidated"
    assert statuses["ev-wifi-api-contract"] == "retained"
    assert statuses["ev-enclosure-base"] == "retained"


def test_unresolved_candidate_dependency_blocks_reuse_instead_of_guessing() -> None:
    baseline = _manifest("vision-a-r1", "camera-A", "camera-A-config")
    candidate = _manifest("vision-b-r1", "camera-A", "camera-A-config")
    camera = next(
        row
        for row in candidate["dependencies"]
        if row["dependency_id"] == "component:camera:sensor_identity"
    )
    camera["resolved"] = False
    camera["value"] = None

    diff = diff_capability_manifests(baseline, candidate)
    assert diff["changed_dependency_ids"] == []
    assert diff["unresolved_dependency_ids"] == ["component:camera:sensor_identity"]

    report = evaluate_evidence_impact(
        {
            "schema_version": "hardware_splicer.evidence_impact_case.v1",
            "changed_dependency_ids": diff["changed_dependency_ids"],
            "unresolved_dependency_ids": diff["unresolved_dependency_ids"],
            "evidence_items": _evidence_rows(),
        }
    )
    statuses = {row["evidence_id"]: row["status"] for row in report["results"]}
    assert statuses["ev-camera-identity"] == "blocked"
    assert statuses["ev-camera-driver-config"] == "blocked"
    assert statuses["ev-optical-benchmark"] == "blocked"
    assert statuses["ev-wifi-api-contract"] == "retained"


def test_recordkeeping_notes_do_not_invalidate_semantically_identical_dependency() -> None:
    baseline = _manifest("vision-a-r1", "camera-A", "camera-A-config")
    candidate = _manifest("vision-a-r2", "camera-A", "camera-A-config")
    candidate["dependencies"][0]["notes"] = "rechecked after documentation cleanup"
    candidate["dependencies"][0]["captured_at"] = "2026-08-17T01:00:00+08:00"

    diff = diff_capability_manifests(baseline, candidate)

    assert "component:camera:sensor_identity" in diff["unchanged_dependency_ids"]
    assert "component:camera:sensor_identity" not in diff["changed_dependency_ids"]


def test_capability_id_mismatch_is_invalid() -> None:
    baseline = _manifest("vision-a-r1", "camera-A", "camera-A-config")
    candidate = _manifest("vision-b-r1", "camera-B", "camera-B-config")
    candidate["capability_id"] = "motion-core"

    diff = diff_capability_manifests(baseline, candidate)

    assert diff["status"] == "invalid"
    assert "capability_id_mismatch" in diff["validation_errors"]
