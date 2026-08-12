from __future__ import annotations

from hardware_splicer.model_first_truth_audit import audit_model_first_truth


def test_clean_model_first_surfaces_pass_without_judging_proposal_quality() -> None:
    report = audit_model_first_truth(
        project_plan={
            "architecture_source": "model_proposed",
            "project_mode_proposal": {"source": "declared", "authority_effect": "none"},
            "robot_genre_proposal": {"source": "model_proposed", "authority_effect": "none"},
            "compatibility_scaffold": {"historical_planner_ran": False},
            "power_on_authorized": False,
        },
        circuit_candidate={
            "result": "blocked",
            "metadata": {
                "dispatch": {
                    "selection_source": "semantic_typed_selection",
                    "legacy_keyword_dispatch_used": False,
                    "authority_effect": "none",
                }
            },
        },
        salvage_package={
            "legacy_planner_architecture_authority": "ignored",
            "recommended_build_id": None,
            "build_selection": {
                "source": "unresolved",
                "legacy_fallback_used": False,
                "authority_effect": "none",
            },
            "physical_identity_authority": "declared_or_validated_exact_only",
            "salvage_resolution": {
                "physical_identity_boundary": {
                    "functional_similarity_is_identity": False,
                    "authority_effect": "none",
                }
            },
            "resolved_modules": [
                {
                    "instance_id": "donor-hbridge",
                    "module_id": None,
                    "source": "donor_functional_salvage_external",
                    "identity_status": "external_unresolved",
                    "external_capability_only": True,
                    "role": "drv",
                    "authority_effect": "none",
                },
                {
                    "instance_id": "gap-driver",
                    "module_id": None,
                    "source": "unresolved_capability_gap",
                    "identity_status": "unresolved",
                    "role": "drv",
                    "authority_effect": "none",
                },
            ],
            "module_overrides": {},
            "splice_plan": {"target": {}},
            "power_on_authorized": False,
        },
        robot_topology={
            "metadata": {
                "part_role_projection": "declared_structured_fields_only",
                "robot_genre_proposal": {
                    "source": "model_proposed",
                    "authority_effect": "none",
                },
                "motion_authorized": False,
            }
        },
        change_impact={
            "metadata": {
                "impact_scope_source": "model_proposed",
                "impact_scope_status": "model_proposed",
                "authority_effect": "none",
            },
            "impacts": [
                {
                    "metadata": {"target_projection": "structural_domain_projection"},
                    "authority_effect": "none",
                }
            ],
            "triggers": [
                {
                    "metadata": {"source_binding": "declared"},
                    "authority_effect": "none",
                }
            ],
            "release_authorized": False,
        },
    )

    assert report["status"] == "pass"
    assert report["violation_count"] == 0
    assert report["checks"]["proposal_correctness_judged"] is False
    assert set(report["surfaces_audited"]) == {
        "project_plan",
        "circuit_candidate",
        "salvage_package",
        "robot_topology",
        "change_impact",
    }


def test_audit_blocks_effective_legacy_semantics_and_open_authority() -> None:
    report = audit_model_first_truth(
        project_plan={
            "architecture_source": "legacy_keyword",
            "project_mode_proposal": {"source": "legacy_heuristic"},
            "compatibility_scaffold": {"historical_planner_ran": True},
            "power_on_authorized": True,
        },
        circuit_candidate={
            "metadata": {
                "dispatch": {
                    "selection_source": "legacy_keyword",
                    "legacy_keyword_dispatch_used": True,
                }
            }
        },
        robot_topology={
            "metadata": {
                "part_role_projection": "legacy_name_keyword",
                "robot_genre_proposal": {"source": "legacy_keyword"},
            },
            "motion_authorized": True,
        },
        change_impact={
            "metadata": {"impact_scope_source": "legacy_keyword"},
            "impacts": [
                {"metadata": {"target_projection": "legacy_text_and_topology"}}
            ],
            "triggers": [
                {"metadata": {"source_binding": "legacy_text_match"}}
            ],
        },
    )

    codes = {row["code"] for row in report["violations"]}
    assert report["status"] == "blocked"
    assert "LEGACY_ARCHITECTURE_AUTHORITY" in codes
    assert "LEGACY_PROJECT_MODE" in codes
    assert "LEGACY_PROJECT_INTAKE_EXECUTED" in codes
    assert "LEGACY_CIRCUIT_DISPATCH" in codes
    assert "LEGACY_CIRCUIT_SELECTION_SOURCE" in codes
    assert "LEGACY_TOPOLOGY_PART_ROLE" in codes
    assert "LEGACY_TOPOLOGY_GENRE" in codes
    assert "LEGACY_IMPACT_SCOPE" in codes
    assert "LEGACY_IMPACT_TARGET_PROJECTION" in codes
    assert "LEGACY_TRIGGER_SOURCE_BINDING" in codes
    assert "PHYSICAL_AUTHORITY_OPEN" in codes


def test_audit_blocks_catalog_standin_for_external_donor_capability() -> None:
    report = audit_model_first_truth(
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
                    "instance_id": "unknown-donor-driver",
                    "module_id": "l298n",
                    "role": "drv",
                    "source": "donor_functional_salvage_external",
                    "identity_status": "external_unresolved",
                    "external_capability_only": True,
                }
            ],
            "module_overrides": {"drv": "l298n"},
            "splice_plan": {"target": {}},
        }
    )

    codes = {row["code"] for row in report["violations"]}
    assert report["status"] == "blocked"
    assert "EXTERNAL_DONOR_STANDIN_IDENTITY" in codes
    assert "UNTRUSTED_CONCRETE_MODULE_BINDING" in codes
    assert "OVERRIDE_WITHOUT_TRUSTED_BINDING" in codes


def test_audit_allows_direct_override_only_for_trusted_bound_or_proposed_module() -> None:
    passing = audit_model_first_truth(
        salvage_package={
            "legacy_planner_architecture_authority": "ignored",
            "recommended_build_id": "sensor_logger",
            "build_selection": {"source": "model_proposed", "legacy_fallback_used": False},
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
                },
                {
                    "instance_id": "design-1",
                    "module_id": "esp32-devkit",
                    "role": "mcu",
                    "source": "workshop_design_proposal",
                    "identity_status": "proposed_design_component",
                    "physical_inventory_identity": False,
                },
            ],
            "module_overrides": {
                "sns": "bme280",
                "mcu": "esp32-devkit",
            },
            "splice_plan": {
                "target": {"recommended_build_id": "sensor_logger"}
            },
        }
    )
    assert passing["status"] == "pass"

    blocked = audit_model_first_truth(
        salvage_package={
            "legacy_planner_architecture_authority": "ignored",
            "recommended_build_id": None,
            "build_selection": {"source": "unresolved", "legacy_fallback_used": False},
            "physical_identity_authority": "declared_or_validated_exact_only",
            "resolved_modules": [],
            "module_overrides": {"drv": "mosfet-irlz44n"},
            "splice_plan": {"target": {}},
        }
    )
    assert blocked["status"] == "blocked"
    assert any(row["code"] == "OVERRIDE_WITHOUT_TRUSTED_BINDING" for row in blocked["violations"])


def test_audit_detects_splice_package_build_truth_divergence() -> None:
    report = audit_model_first_truth(
        salvage_package={
            "legacy_planner_architecture_authority": "ignored",
            "recommended_build_id": None,
            "build_selection": {"source": "unresolved", "legacy_fallback_used": False},
            "physical_identity_authority": "declared_or_validated_exact_only",
            "resolved_modules": [],
            "module_overrides": {},
            "splice_plan": {
                "target": {"recommended_build_id": "automatic_plant_watering"}
            },
        }
    )
    assert report["status"] == "blocked"
    violation = next(
        row
        for row in report["violations"]
        if row["code"] == "SPLICE_BUILD_TRUTH_DIVERGENCE"
    )
    assert violation["observed"] == {
        "package": None,
        "splice_plan": "automatic_plant_watering",
    }
