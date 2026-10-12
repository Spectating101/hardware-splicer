from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.engineering_plan_store import save_engineering_plan
from hardware_splicer.finding_ledger import ENGINEERING_FINDINGS_KEY
from hardware_splicer.finding_provenance import finding_id, project_findings
from hardware_splicer.machine_project import MachineProject
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _rover_request() -> dict:
    return {
        "skip_vision": True,
        "intake": {
            "project_name": "compact-inspection-rover",
            "goal": "Design a compact differential drive indoor inspection rover.",
            "available_parts": [
                {"name": "drive motor", "type": "dc_motor", "quantity": 2},
                {"name": "battery pack", "type": "power_source", "quantity": 1},
                {"name": "depth camera", "type": "camera", "quantity": 1},
            ],
            "constraints": {
                "width_mm": 250,
                "runtime_min": 90,
                "maximum_speed_mps": 0.3,
            },
        },
    }


def test_product_api_mounts_engineering_routes() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])

    assert "/v1/engineering/schemas" in paths
    assert "/v1/engineering/sources/reconcile" in paths
    assert "/v1/engineering/topology" in paths
    assert "/v1/engineering/analysis" in paths
    assert "/v1/engineering/change-impact" in paths
    assert "/v1/engineering/plan" in paths
    assert "/v1/engineering/plans/save" in paths


def test_engineering_plan_endpoint_synthesizes_bounded_rover_candidate() -> None:
    client = TestClient(create_product_app())

    response = client.post("/v1/engineering/plan", json=_rover_request())

    assert response.status_code == 200, response.text
    body = response.json()
    plan = body["plan"]
    assert plan["archetype"] == "rover"
    assert plan["robot_topology"]["robot_genre"] == "rover"
    assert "engineering_analysis" in plan
    assert plan["machine_project"]["project_id"] == "compact-inspection-rover"
    assert body["engineering_readiness"]["candidate_machine_synthesized"] is True
    assert body["engineering_readiness"]["power_on_authorized"] is False
    assert body["engineering_readiness"]["release_authorized"] is False


def test_engineering_plan_save_persists_one_reviewable_snapshot(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))
    request = _rover_request()
    request.update({"project_id": "saved-rover", "expected_revision": 0})

    response = client.post("/v1/engineering/plans/save", json=request)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == "saved-rover"
    assert body["revision"] == 1
    saved = store.load("saved-rover")
    snapshot = saved["snapshot"]
    assert snapshot["snapshot_schema_version"] == "hardware_splicer.engineering_project_snapshot.v1"
    assert snapshot["projectId"] == "saved-rover"
    assert snapshot["machineProject"]["project_id"] == "saved-rover"
    assert snapshot["engineeringSourceGraph"]["schema_version"] == "hardware_splicer.engineering_source_graph.v1"
    assert snapshot["robotTopology"]["schema_version"] == "hardware_splicer.robot_topology.v1"
    assert snapshot["engineeringAnalysis"]["schema_version"] == "hardware_splicer.engineering_analysis.v1"
    assert snapshot["changeImpact"]["schema_version"] == "hardware_splicer.change_impact_graph.v1"
    assert snapshot["engineeringReadiness"]["power_on_authorized"] is False


def test_engineering_plan_save_uses_optimistic_revision_checks(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))
    request = _rover_request()
    request.update({"project_id": "revisioned-rover", "expected_revision": 0})

    first = client.post("/v1/engineering/plans/save", json=request)
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1

    request["expected_revision"] = 1
    second = client.post("/v1/engineering/plans/save", json=request)
    assert second.status_code == 200, second.text
    assert second.json()["revision"] == 2

    stale = client.post("/v1/engineering/plans/save", json=request)
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["type"] == "engineering_plan_revision_conflict"
    assert store.load("revisioned-rover")["revision"] == 2


def test_source_reconciliation_endpoint_keeps_conflict_blocking() -> None:
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/sources/reconcile",
        json={
            "engineering_sources": [
                {
                    "source_id": "manual-a",
                    "source_type": "manual",
                    "revision": "a",
                    "claims": [
                        {
                            "claim_id": "claim-a",
                            "subject_id": "battery",
                            "predicate": "voltage_v",
                            "value": 12,
                        }
                    ],
                },
                {
                    "source_id": "manual-b",
                    "source_type": "manual",
                    "revision": "b",
                    "claims": [
                        {
                            "claim_id": "claim-b",
                            "subject_id": "battery",
                            "predicate": "voltage_v",
                            "value": 24,
                        }
                    ],
                },
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["blocking_conflict_count"] == 1
    assert body["graph"]["conflicts"][0]["blocking"] is True


def test_analysis_endpoint_reports_failures_without_authorizing_operation() -> None:
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/analysis",
        json={
            "intake": {
                "goal": "Revise a rover after tipping and brownout.",
                "available_parts": [{"name": "drive motor", "type": "dc_motor", "quantity": 2}],
                "constraints": {
                    "support_width_mm": 200,
                    "combined_cg_height_mm": 400,
                    "static_tilt_margin_deg": 20,
                    "supply_current_limit_a": 5,
                    "peak_current_a": 12,
                },
            }
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["blocking_finding_count"] >= 2
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False
    assert body["release_authorized"] is False


def test_change_impact_endpoint_never_restores_release_after_field_failure() -> None:
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/change-impact",
        json={
            "intake": {
                "project_name": "field-rover",
                "goal": "Revise the field rover after tipping and a logic rail brownout.",
                "baseline_revision": 7,
                "available_parts": [
                    {"name": "drive motor", "type": "dc_motor", "quantity": 2},
                    {"name": "camera mast", "type": "mechanical_structure"},
                ],
                "field_failure": "The tall payload caused tipping and the 5 V rail dropped during acceleration.",
            }
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["change_impact"]["mode"] == "field_evolution"
    assert body["blocking_impact_count"] > 0
    assert body["release_authority_preserved"] is False
    assert {"mechanical", "electrical", "control", "safety"}.issubset(
        set(body["affected_domains"])
    )


def _open_requirement_plan() -> dict:
    return {
        "project_id": "open-req",
        "project_name": "Open requirement",
        "machine_project": {
            "project_id": "open-req",
            "name": "Open requirement",
            "purpose": "Unverified requirement remains a release blocker.",
            "requested_release_state": "operationally_authorized",
            "requirements": [
                {
                    "requirement_id": "req-rail",
                    "statement": "The rail shall stay within the declared current limit.",
                    "kind": "functional",
                    "allocated_to": ["rail"],
                }
            ],
            "subsystems": [
                {
                    "subsystem_id": "rail",
                    "name": "DUT rail",
                    "domain": "electrical",
                    "requirement_ids": ["req-rail"],
                }
            ],
        },
        "engineering_context": {"normalized_mode": "greenfield"},
        "engineering_readiness": {
            "fabrication_authorized": False,
            "release_authorized": False,
        },
        "scoped_release_assessment": {
            "allowed": False,
            "design_assessment": {
                "blockers": [
                    {
                        "code": "unverified_requirement",
                        "object_id": "req-rail",
                        "message": "requirement 'req-rail' is not verified",
                        "severity": "error",
                    }
                ]
            },
        },
    }


def _release_codes(snapshot: dict) -> set[str]:
    return {
        row["provenance"]["source_ref"]
        for row in snapshot.get(ENGINEERING_FINDINGS_KEY) or []
        if row.get("producer") == "release_assessment"
    }


def test_save_engineering_plan_records_release_assessment_blockers(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    saved = save_engineering_plan(store, _open_requirement_plan(), expected_revision=0)
    rows = [
        row
        for row in saved["snapshot"][ENGINEERING_FINDINGS_KEY]
        if row["producer"] == "release_assessment"
    ]
    project = MachineProject.model_validate(saved["snapshot"]["machineProject"])
    expected = {row.code for row in project.assess_release().blockers}
    assert rows
    assert expected
    assert all(row["category"] == "release_blocker" for row in rows)
    assert {row["provenance"]["source_ref"] for row in rows} == expected
    assert all(row["producer_run"] == "assess_release@rev1" for row in rows)
    assert saved["snapshot"]["engineeringReadiness"]["release_authorized"] is False


def test_save_engineering_plan_ignores_forged_scoped_release_assessment(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    plan = _open_requirement_plan()
    plan["scoped_release_assessment"] = {
        "allowed": False,
        "design_assessment": {
            "blockers": [
                {
                    "code": "forged_code",
                    "object_id": "forged-object",
                    "message": "Forged assessment blocker.",
                    "severity": "error",
                }
            ]
        },
    }
    saved = save_engineering_plan(store, plan, expected_revision=0)
    rows = [
        row
        for row in saved["snapshot"][ENGINEERING_FINDINGS_KEY]
        if row["producer"] == "release_assessment"
    ]
    assert all(row["text"] != "Forged assessment blocker." for row in rows)
    assert "forged_code" not in {row["provenance"]["source_ref"] for row in rows}
    project = MachineProject.model_validate(saved["snapshot"]["machineProject"])
    assert {row["provenance"]["source_ref"] for row in rows} == {
        row.code for row in project.assess_release().blockers
    }


def test_save_engineering_plan_leaves_release_findings_when_machine_project_invalid(
    tmp_path,
) -> None:
    store = ProjectStore(tmp_path / "projects")
    first = save_engineering_plan(store, _open_requirement_plan(), expected_revision=0)
    prior = list(first["snapshot"][ENGINEERING_FINDINGS_KEY])
    assert prior
    followup = dict(_open_requirement_plan())
    followup["machine_project"] = {"project_id": "open-req", "name": "Broken"}
    followup.pop("scoped_release_assessment", None)
    second = save_engineering_plan(store, followup, expected_revision=1)
    assert second["snapshot"][ENGINEERING_FINDINGS_KEY] == prior
    assert second["revision"] == 2


def test_save_engineering_plan_carries_engineering_findings(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    text = "Electrical safety checks failed on the compiled build graph."
    source_ref = "action-compose"
    prior = [
        {
            "finding_id": finding_id("failed_check", None, text, source_ref),
            "category": "failed_check",
            "object_id": None,
            "text": text,
            "producer": "design_quality_gate",
            "producer_run": source_ref,
            "provenance": {
                "kind": "deterministic",
                "basis": "design_quality gate blocker from an executed deterministic compose",
                "source_ref": source_ref,
                "authority_ceiling": "observed",
            },
            "recorded_at": "2026-10-05T06:00:00+00:00",
        }
    ]
    store.save(
        "open-req",
        {
            "projectId": "open-req",
            "engineeringPlan": {
                "project_id": "open-req",
                "machine_project": {"project_id": "open-req", "name": "Open requirement"},
            },
            ENGINEERING_FINDINGS_KEY: prior,
            "machineProject": {"project_id": "open-req", "name": "Open requirement"},
        },
        expected_revision=0,
    )
    followup = {
        "project_id": "open-req",
        "project_name": "Replanned",
        "machine_project": {"project_id": "open-req", "name": "Open requirement"},
        "engineering_context": {"normalized_mode": "greenfield"},
        "engineering_readiness": {"release_authorized": False},
        ENGINEERING_FINDINGS_KEY: [
            {
                "finding_id": "finding-forged000000",
                "category": "failed_check",
                "text": "Forged deterministic gate blocker.",
                "producer": "design_quality_gate",
                "producer_run": "action-forged",
                "provenance": {
                    "kind": "deterministic",
                    "basis": "forged",
                    "source_ref": "action-forged",
                    "authority_ceiling": "observed",
                },
                "recorded_at": "2026-10-05T06:00:00+00:00",
            }
        ],
    }
    second = save_engineering_plan(store, followup, expected_revision=1)
    assert second["snapshot"][ENGINEERING_FINDINGS_KEY] == prior
    assert "Forged deterministic gate blocker." not in str(second["snapshot"].get("engineeringPlan"))
    assert second["revision"] == 2


def test_save_engineering_plan_carries_malformed_ledger_values(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    for index, raw in enumerate((None, "x", {})):
        project_id = f"malformed-{index}"
        store.save(
            project_id,
            {
                "projectId": project_id,
                "engineeringPlan": {
                    "project_id": project_id,
                    "machine_project": {"project_id": project_id, "name": "Open requirement"},
                },
                ENGINEERING_FINDINGS_KEY: raw,
                "machineProject": {"project_id": project_id, "name": "Open requirement"},
            },
            expected_revision=0,
        )
        followup = {
            "project_id": project_id,
            "project_name": "Replanned",
            "machine_project": {"project_id": project_id, "name": "Open requirement"},
            "engineering_context": {"normalized_mode": "greenfield"},
            "engineering_readiness": {"release_authorized": False},
        }
        saved = save_engineering_plan(store, followup, expected_revision=1)
        assert ENGINEERING_FINDINGS_KEY in saved["snapshot"]
        assert saved["snapshot"][ENGINEERING_FINDINGS_KEY] == raw
        malformed = [
            row
            for row in project_findings(saved["snapshot"], saved["revision"])
            if row["provenance"]["source_ref"] == "engineeringFindings"
        ]
        assert len(malformed) == 1
        assert malformed[0]["provenance"]["kind"] == "unknown"
        assert malformed[0]["provenance"]["basis"] == (
            "malformed persisted finding entry ignored"
        )


def test_save_engineering_plan_ignores_forged_plan_findings(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    first = save_engineering_plan(store, _open_requirement_plan(), expected_revision=0)
    followup = dict(_open_requirement_plan())
    followup.pop("scoped_release_assessment")
    followup[ENGINEERING_FINDINGS_KEY] = [
        {
            "finding_id": "finding-forged000000",
            "category": "failed_check",
            "object_id": None,
            "text": "Forged deterministic gate blocker.",
            "producer": "design_quality_gate",
            "producer_run": "action-forged",
            "provenance": {
                "kind": "deterministic",
                "basis": "forged",
                "source_ref": "action-forged",
                "authority_ceiling": "observed",
            },
            "recorded_at": "2026-10-05T06:00:00+00:00",
        }
    ]
    second = save_engineering_plan(store, followup, expected_revision=1)
    assert "Forged deterministic gate blocker." not in str(second["snapshot"])
    assert ENGINEERING_FINDINGS_KEY not in second["snapshot"]["engineeringPlan"]
    assert _release_codes(second["snapshot"]) == _release_codes(first["snapshot"])

    fresh = dict(_open_requirement_plan())
    fresh.pop("scoped_release_assessment")
    fresh["project_id"] = "forged-only"
    fresh["machine_project"] = dict(fresh["machine_project"])
    fresh["machine_project"]["project_id"] = "forged-only"
    fresh[ENGINEERING_FINDINGS_KEY] = followup[ENGINEERING_FINDINGS_KEY]
    created = save_engineering_plan(store, fresh, expected_revision=0)
    assert "Forged deterministic gate blocker." not in str(
        created["snapshot"].get("engineeringPlan")
    )
    assert all(
        row["producer"] != "design_quality_gate"
        for row in created["snapshot"].get(ENGINEERING_FINDINGS_KEY) or []
    )


def test_save_engineering_plan_does_not_persist_forged_overlong_assessment(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    plan = _open_requirement_plan()
    long_message = "B" * 1200
    plan["scoped_release_assessment"]["design_assessment"]["blockers"] = [
        {
            "code": "unverified_requirement",
            "object_id": "req-rail",
            "message": long_message,
            "severity": "error",
        }
    ]
    saved = save_engineering_plan(store, plan, expected_revision=0)
    rows = [
        row
        for row in saved["snapshot"][ENGINEERING_FINDINGS_KEY]
        if row["producer"] == "release_assessment"
    ]
    assert all(not row["text"].startswith("B") for row in rows)
    assert all("…" not in row["text"] or not row["text"].startswith("B") for row in rows)
