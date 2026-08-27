from __future__ import annotations

from hardware_splicer.outer_engineer_audit import audit_outer_engineer_run


def test_outer_audit_passes_clean_constitution_and_identity_closure() -> None:
    report = audit_outer_engineer_run(
        project_plan={
            "architecture_source": "model_proposed",
            "compatibility_scaffold": {"historical_planner_ran": False},
            "power_on_authorized": False,
        },
        salvage_package={
            "legacy_planner_architecture_authority": "ignored",
            "recommended_build_id": None,
            "build_selection": {"source": "unresolved", "legacy_fallback_used": False},
            "physical_identity_authority": "declared_or_validated_exact_only",
            "salvage_resolution": {
                "physical_identity_boundary": {"functional_similarity_is_identity": False}
            },
            "resolved_modules": [
                {
                    "instance_id": "sensor-1",
                    "module_id": "bme280",
                    "role": "sns",
                    "source": "declared_catalog_identity",
                    "identity_status": "declared",
                }
            ],
            "module_overrides": {"sns": "bme280"},
            "splice_plan": {"target": {}},
            "graph_input": {"nodes": [{"module_id": "bme280"}]},
            "firmware_scaffold": {"sensor_module_id": "bme280"},
            "release_authorized": False,
        },
    )

    assert report["status"] == "pass"
    assert report["constitution"]["status"] == "pass"
    assert report["identity_closure"]["status"] == "pass"
    assert report["blocking_finding_count"] == 0
    assert report["recommended_outer_action"].startswith("continue to proposal-quality")


def test_outer_audit_blocks_contract_leak_before_model_reasoning_review() -> None:
    report = audit_outer_engineer_run(
        circuit_candidate={
            "metadata": {
                "dispatch": {
                    "selection_source": "legacy_keyword",
                    "legacy_keyword_dispatch_used": True,
                }
            }
        },
        salvage_package={
            "legacy_planner_architecture_authority": "ignored",
            "recommended_build_id": None,
            "build_selection": {"source": "unresolved", "legacy_fallback_used": False},
            "physical_identity_authority": "declared_or_validated_exact_only",
            "resolved_modules": [],
            "module_overrides": {},
            "splice_plan": {"target": {}},
            "firmware_scaffold": {"driver_module_id": "l298n"},
        },
    )

    assert report["status"] == "blocked"
    assert report["constitution"]["status"] == "blocked"
    assert report["identity_closure"]["status"] == "blocked"
    assert report["diagnostic_contract"]["model_reasoning_judged"] is False
    assert "repair contract/system leakage" in report["recommended_outer_action"]


def test_outer_audit_marks_future_bom_identity_for_review_not_hard_failure() -> None:
    report = audit_outer_engineer_run(
        salvage_package={
            "legacy_planner_architecture_authority": "ignored",
            "recommended_build_id": None,
            "build_selection": {"source": "unresolved", "legacy_fallback_used": False},
            "physical_identity_authority": "declared_or_validated_exact_only",
            "resolved_modules": [],
            "module_overrides": {},
            "splice_plan": {"target": {}},
            "bom_estimate": {
                "items": [
                    {"module_id": "mosfet-irlz44n", "reason": "candidate purchase"}
                ]
            },
        }
    )

    assert report["status"] == "review"
    assert report["constitution"]["status"] == "pass"
    assert report["identity_closure"]["status"] == "review"
    assert report["blocking_finding_count"] == 0
    assert report["review_finding_count"] == 1
    assert "review proposed/unbound downstream design identities" in report["recommended_outer_action"]
