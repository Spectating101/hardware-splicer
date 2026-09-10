from __future__ import annotations

import copy
import json

from hardware_splicer.cleanroom_unseen_spi_flash_experiment import spi_flash_adapter_snapshot
from hardware_splicer.codex_progress_provenance import audit_codex_progress_provenance


PROJECT_ID = "exp-1"


def _wrap_call(*, operation_id: str, method: str, path: str, arguments: dict, body: object) -> dict:
    payload = {
        "ok": True,
        "status_code": 200,
        "content_type": "application/json",
        "byte_length": 2,
        "sha256": "0" * 64,
        "headers": {"content-type": "application/json"},
        "body": body,
        "operation_id": operation_id,
        "method": method,
        "path": path,
    }
    wrapper = {
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "structured_content": None,
    }
    return {
        "type": "mcp_call",
        "name": "hs_backend_call",
        "arguments": arguments,
        "status": "completed",
        "error": None,
        "output": json.dumps(wrapper),
    }


def _save(snapshot: dict, *, revision: int) -> dict:
    return _wrap_call(
        operation_id="save_project_snapshot",
        method="PUT",
        path=f"/v1/projects/{PROJECT_ID}/snapshot",
        arguments={
            "operation_id": "save_project_snapshot",
            "path_params": {"project_id": PROJECT_ID},
            "json_body": {"snapshot": snapshot, "expected_revision": revision - 1},
        },
        body={"ok": True, "project": {"project_id": PROJECT_ID, "revision": revision}},
    )


def _mutation(
    *,
    operation_id: str,
    path: str,
    revision: int,
    payload_key: str,
    payload_value: object,
) -> dict:
    return _wrap_call(
        operation_id=operation_id,
        method="POST",
        path=path,
        arguments={
            "operation_id": operation_id,
            "path_params": {"project_id": PROJECT_ID},
            "json_body": {"expected_revision": revision - 1},
        },
        body={
            "ok": True,
            "project_id": PROJECT_ID,
            "revision": revision,
            payload_key: payload_value,
        },
    )


def _read(snapshot: dict, *, revision: int) -> dict:
    return _wrap_call(
        operation_id="get_project",
        method="GET",
        path=f"/v1/projects/{PROJECT_ID}",
        arguments={
            "operation_id": "get_project",
            "path_params": {"project_id": PROJECT_ID},
        },
        body={
            "ok": True,
            "project": {
                "schema_version": "hardware_splicer.project_snapshot.v1",
                "project_id": PROJECT_ID,
                "revision": revision,
                "saved_at": "2026-09-11T00:00:00+00:00",
                "snapshot": snapshot,
                "metadata": {},
            },
        },
    )


def _mission_progress(*surfaces: str, passed: bool = True) -> dict:
    return {
        "contract_pass": passed,
        "changed_mission_surfaces": list(surfaces),
    }


def _audit(initial: dict, progress: dict, *calls: dict) -> dict:
    return audit_codex_progress_provenance(
        {"output": list(calls)},
        expected_project_id=PROJECT_ID,
        initial_snapshot=initial,
        mission_progress=progress,
    )


def test_plan_payload_exactly_linked_to_final_engineering_plan_passes() -> None:
    initial = spi_flash_adapter_snapshot()
    plan = {
        "schema_version": "synthetic-plan.v1",
        "authority_effect": "none",
        "steps": [{"id": "resolve-package", "status": "proposed"}],
    }
    final = copy.deepcopy(initial)
    final["engineeringPlan"] = plan

    result = _audit(
        initial,
        _mission_progress("engineeringPlan"),
        _save(initial, revision=1),
        _mutation(
            operation_id="plan_project",
            path=f"/v1/projects/{PROJECT_ID}/engineering/plan",
            revision=2,
            payload_key="plan",
            payload_value=plan,
        ),
        _read(final, revision=2),
    )

    assert result["contract_pass"] is True
    assert result["checks"]["operation_payload_matches_changed_final_surface"] is True
    assert result["operation_surface_links"][0]["final_surface"] == "engineeringPlan"
    assert result["operation_surface_links"][0]["response_payload_path"] == "$.plan"
    assert result["operation_surface_links"][0]["reported_project_revision"] == 2


def test_generic_save_plus_administrative_revision_bump_cannot_launder_engineering_plan() -> None:
    initial = spi_flash_adapter_snapshot()
    fake_plan = {"schema_version": "invented-plan", "claim": "model inserted this generically"}
    package = {"package_id": "pkg-1", "status": "draft"}
    final = copy.deepcopy(initial)
    final["engineeringPlan"] = fake_plan
    final["engineeringPackages"] = [package]

    result = _audit(
        initial,
        _mission_progress("engineeringPlan", "engineeringPackages"),
        _save(initial, revision=1),
        _save(final, revision=2),
        _mutation(
            operation_id="create_engineering_package",
            path=f"/v1/projects/{PROJECT_ID}/engineering-package",
            revision=3,
            payload_key="package",
            payload_value=package,
        ),
        _read(final, revision=3),
    )

    assert result["checks"]["revision_linked_project_mutation_present"] is True
    assert result["checks"]["creditable_changed_engineering_surface_present"] is True
    assert result["checks"]["operation_payload_matches_changed_final_surface"] is False
    assert result["revision_linked_candidates"][0]["operation_id"] == "create_engineering_package"
    assert result["operation_surface_links"] == []
    assert result["contract_pass"] is False


def test_administrative_surface_is_not_creditable_even_when_payload_matches_exactly() -> None:
    initial = spi_flash_adapter_snapshot()
    package = {"package_id": "pkg-1", "status": "draft"}
    final = copy.deepcopy(initial)
    final["engineeringPackages"] = [package]

    result = _audit(
        initial,
        _mission_progress("engineeringPackages"),
        _save(initial, revision=1),
        _mutation(
            operation_id="create_engineering_package",
            path=f"/v1/projects/{PROJECT_ID}/engineering-package",
            revision=2,
            payload_key="packages",
            payload_value=[package],
        ),
        _read(final, revision=2),
    )

    assert result["creditable_changed_surfaces"] == []
    assert result["checks"]["creditable_changed_engineering_surface_present"] is False
    assert result["contract_pass"] is False


def test_response_subset_does_not_prove_larger_final_surface() -> None:
    initial = spi_flash_adapter_snapshot()
    returned_plan = {"schema_version": "synthetic-plan.v1"}
    final_plan = {**returned_plan, "steps": [{"id": "invented-afterward"}]}
    final = copy.deepcopy(initial)
    final["engineeringPlan"] = final_plan

    result = _audit(
        initial,
        _mission_progress("engineeringPlan"),
        _save(initial, revision=1),
        _mutation(
            operation_id="plan_project",
            path=f"/v1/projects/{PROJECT_ID}/engineering/plan",
            revision=2,
            payload_key="plan",
            payload_value=returned_plan,
        ),
        _read(final, revision=2),
    )

    assert result["checks"]["revision_linked_project_mutation_present"] is True
    assert result["checks"]["operation_payload_matches_changed_final_surface"] is False
    assert result["contract_pass"] is False


def test_nested_exact_operation_payload_can_prove_final_surface() -> None:
    initial = spi_flash_adapter_snapshot()
    plan = {"schema_version": "synthetic-plan.v1", "steps": [{"id": "one"}]}
    final = copy.deepcopy(initial)
    final["engineeringPlan"] = plan
    nested = {"result": {"plan": plan}}

    result = _audit(
        initial,
        _mission_progress("engineeringPlan"),
        _save(initial, revision=1),
        _mutation(
            operation_id="plan_project",
            path=f"/v1/projects/{PROJECT_ID}/engineering/plan",
            revision=2,
            payload_key="payload",
            payload_value=nested,
        ),
        _read(final, revision=2),
    )

    assert result["contract_pass"] is True
    assert any(
        row["response_payload_path"].endswith(".plan")
        for row in result["operation_surface_links"]
    )


def test_wrong_revision_operation_payload_cannot_prove_final_surface() -> None:
    initial = spi_flash_adapter_snapshot()
    plan = {"schema_version": "synthetic-plan.v1"}
    final = copy.deepcopy(initial)
    final["engineeringPlan"] = plan

    result = _audit(
        initial,
        _mission_progress("engineeringPlan"),
        _save(initial, revision=1),
        _mutation(
            operation_id="plan_project",
            path=f"/v1/projects/{PROJECT_ID}/engineering/plan",
            revision=2,
            payload_key="plan",
            payload_value=plan,
        ),
        _save(final, revision=3),
        _read(final, revision=3),
    )

    assert result["final_project_revision"] == 3
    assert result["revision_linked_candidates"] == []
    assert result["checks"]["revision_linked_project_mutation_present"] is False
    assert result["contract_pass"] is False


def test_unscoped_operation_with_matching_payload_cannot_take_credit() -> None:
    initial = spi_flash_adapter_snapshot()
    plan = {"schema_version": "synthetic-plan.v1"}
    final = copy.deepcopy(initial)
    final["engineeringPlan"] = plan
    unrelated = _wrap_call(
        operation_id="global_analysis",
        method="POST",
        path="/v1/analysis",
        arguments={"operation_id": "global_analysis", "json_body": {}},
        body={
            "ok": True,
            "project_id": PROJECT_ID,
            "revision": 2,
            "plan": plan,
        },
    )

    result = _audit(
        initial,
        _mission_progress("engineeringPlan"),
        _save(initial, revision=1),
        unrelated,
        _read(final, revision=2),
    )

    # A project id appearing only in the response is not sufficient evidence that the
    # operation was scoped through a project route or arguments.
    assert result["checks"]["revision_linked_project_mutation_present"] is False
    assert result["contract_pass"] is False


def test_failed_mission_progress_prevents_provenance_pass_even_with_matching_payload() -> None:
    initial = spi_flash_adapter_snapshot()
    plan = {"schema_version": "synthetic-plan.v1"}
    final = copy.deepcopy(initial)
    final["engineeringPlan"] = plan
    result = _audit(
        initial,
        _mission_progress("engineeringPlan", passed=False),
        _save(initial, revision=1),
        _mutation(
            operation_id="plan_project",
            path=f"/v1/projects/{PROJECT_ID}/engineering/plan",
            revision=2,
            payload_key="plan",
            payload_value=plan,
        ),
        _read(final, revision=2),
    )
    assert result["checks"]["operation_payload_matches_changed_final_surface"] is True
    assert result["checks"]["mission_progress_contract_pass"] is False
    assert result["contract_pass"] is False
