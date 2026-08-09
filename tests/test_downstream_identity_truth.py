from __future__ import annotations

from hardware_splicer.downstream_identity_truth import (
    build_model_first_bringup_card,
    build_model_first_firmware_scaffold,
    build_model_first_gap_analysis,
    build_model_first_mechanism_pack,
)
from hardware_splicer.identity_propagation_audit import audit_identity_propagation
from hardware_splicer.model_first_truth_audit import audit_model_first_truth


def _unresolved_rows():
    return [
        {
            "instance_id": "mcu-1",
            "module_id": "esp32-devkit",
            "role": "mcu",
            "source": "declared_catalog_identity",
            "identity_status": "declared",
        },
        {
            "instance_id": "motor-1",
            "module_id": None,
            "role": "mot",
            "source": "unresolved_identity",
            "identity_status": "unresolved",
        },
        {
            "instance_id": "driver-gap",
            "module_id": None,
            "role": "drv",
            "source": "unresolved_capability_gap",
            "identity_status": "unresolved",
        },
    ]


def test_model_first_gap_analysis_keeps_unknowns_symbolic() -> None:
    report = build_model_first_gap_analysis(
        resolved_modules=_unresolved_rows(),
        power_topology=None,
    )

    assert report["mode"] == "model_first_structured"
    assert report["ready_to_compile"] is False
    assert report["inventory_module_ids"] == ["esp32-devkit"]
    assert report["goal_module_ids"] == []
    assert report["shopping_list"] == []
    assert report["semantic_goal_routing_used"] is False
    assert report["concrete_gap_substitution_used"] is False
    assert all(row.get("module_id") is None for row in report["still_missing"])


def test_model_first_bringup_does_not_auto_wire_unknown_hardware() -> None:
    card = build_model_first_bringup_card(
        goal="Make the unknown motor spin with a familiar driver",
        resolved_modules=_unresolved_rows(),
        power_topology=None,
    )

    assert card["mode"] == "model_first_evidence_only"
    assert card["module_ids"] == ["esp32-devkit"]
    assert card["connections"] == []
    assert card["gpio_assignments"] == []
    assert card["auto_wire_used"] is False
    assert card["unresolved_questions"]


def test_model_first_firmware_does_not_generate_goal_selected_template_or_default_pins() -> None:
    rows = _unresolved_rows()
    bringup = build_model_first_bringup_card(
        goal="robot fan servo pump",
        resolved_modules=rows,
        power_topology=None,
    )
    firmware = build_model_first_firmware_scaffold(
        build_id=None,
        resolved_modules=rows,
        bringup_card=bringup,
    )

    assert firmware["status"] == "blocked_evidence_required"
    assert firmware["filename"] is None
    assert firmware["pins"] == {}
    assert firmware["source"] == ""
    assert firmware["generator"] == "none_model_first_evidence_gate"
    assert firmware["firmware_flash_authorized"] is False


def test_model_first_mechanism_does_not_invent_sg90_or_geometry_from_goal() -> None:
    pack = build_model_first_mechanism_pack(
        resolved_modules=_unresolved_rows(),
        constraints={},
    )

    assert pack["status"] == "blocked_evidence_required"
    assert pack["kind"] is None
    assert pack["project_spec"] == {}
    assert pack["outputs"] == []
    assert pack["motion_authorized"] is False
    assert "geometry" in pack["claim_boundary"].lower()


def test_fail_closed_downstream_package_passes_identity_propagation_without_standins() -> None:
    rows = _unresolved_rows()
    bringup = build_model_first_bringup_card(
        goal="unknown motor",
        resolved_modules=rows,
        power_topology=None,
    )
    package = {
        "resolved_modules": rows,
        "graph_input": {},
        "bringup_card": bringup,
        "firmware_scaffold": build_model_first_firmware_scaffold(
            build_id=None,
            resolved_modules=rows,
            bringup_card=bringup,
        ),
        "mechanism_pack": build_model_first_mechanism_pack(
            resolved_modules=rows,
            constraints={},
        ),
        "bom_estimate": {"items": []},
    }

    audit = audit_identity_propagation(package)

    assert audit["status"] == "pass"
    assert audit["blocking_finding_count"] == 0
    assert audit["finding_count"] == 0


def test_truth_audit_accepts_explicit_legacy_nonexecution_state() -> None:
    package = {
        "legacy_planner_architecture_authority": "not_executed",
        "legacy_planner_context": {"executed": False},
        "recommended_build_id": None,
        "build_selection": {"source": "unresolved", "legacy_fallback_used": False},
        "physical_identity_authority": "declared_or_validated_exact_only",
        "resolved_modules": _unresolved_rows(),
        "module_overrides": {},
        "splice_plan": {"target": {}},
        "identity_propagation_audit": {
            "status": "pass",
            "findings": [],
        },
    }

    report = audit_model_first_truth(salvage_package=package)

    assert report["status"] == "pass"
    assert report["violation_count"] == 0
    assert report["checks"]["downstream_identity_propagation_checked"] is True


def test_truth_audit_rejects_false_nonexecution_claim_and_downstream_identity_leak() -> None:
    package = {
        "legacy_planner_architecture_authority": "not_executed",
        "legacy_planner_context": {"executed": True},
        "recommended_build_id": None,
        "build_selection": {"source": "unresolved", "legacy_fallback_used": False},
        "physical_identity_authority": "declared_or_validated_exact_only",
        "resolved_modules": _unresolved_rows(),
        "module_overrides": {},
        "splice_plan": {"target": {}},
        "identity_propagation_audit": {
            "status": "blocked",
            "findings": [
                {
                    "severity": "blocking",
                    "surface": "firmware_scaffold",
                    "path": "firmware_scaffold.driver_module_id",
                    "module_id": "l298n",
                    "message": "Untrusted driver identity reached firmware.",
                }
            ],
        },
    }

    report = audit_model_first_truth(salvage_package=package)
    codes = {row["code"] for row in report["violations"]}

    assert report["status"] == "blocked"
    assert "LEGACY_SALVAGE_EXECUTION_STATE_DIVERGENCE" in codes
    assert "DOWNSTREAM_IDENTITY_PROPAGATION" in codes
