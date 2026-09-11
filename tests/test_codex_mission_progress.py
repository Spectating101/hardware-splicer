from __future__ import annotations

import copy
import json

from hardware_splicer.cleanroom_unseen_spi_flash_experiment import (
    build_unseen_spi_flash_cases,
    spi_flash_adapter_snapshot,
)
from hardware_splicer.codex_mission_progress import (
    audit_codex_mission_progress,
    canonical_blocker_catalog,
)


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


def _project_body(snapshot: dict, *, revision: int) -> dict:
    return {
        "ok": True,
        "project": {
            "schema_version": "hardware_splicer.project_snapshot.v1",
            "project_id": PROJECT_ID,
            "revision": revision,
            "saved_at": "2026-09-11T00:00:00+00:00",
            "snapshot": snapshot,
            "metadata": {},
        },
    }


def _save(snapshot: dict, *, revision: int = 1) -> dict:
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


def _plan(*, expected_revision: int = 1, reported_revision: int | None = None) -> dict:
    revision = reported_revision if reported_revision is not None else expected_revision + 1
    return _wrap_call(
        operation_id="plan_project",
        method="POST",
        path=f"/v1/projects/{PROJECT_ID}/engineering/plan",
        arguments={
            "operation_id": "plan_project",
            "path_params": {"project_id": PROJECT_ID},
            "json_body": {"expected_revision": expected_revision, "intake": {}},
        },
        body={
            "ok": True,
            "project_id": PROJECT_ID,
            "revision": revision,
            "plan": {"schema_version": "synthetic-plan"},
        },
    )


def _read(snapshot: dict, *, revision: int = 2) -> dict:
    return _wrap_call(
        operation_id="get_project",
        method="GET",
        path=f"/v1/projects/{PROJECT_ID}",
        arguments={
            "operation_id": "get_project",
            "path_params": {"project_id": PROJECT_ID},
        },
        body=_project_body(snapshot, revision=revision),
    )


def _progress_snapshot(initial: dict) -> dict:
    final = copy.deepcopy(initial)
    final.update(
        {
            "currentStage": "guided_engineering_plan",
            "engineeringPlan": {
                "schema_version": "hardware_splicer.guided_engineering_plan.synthetic",
                "authority_effect": "none",
            },
            "orderedSteps": [
                {
                    "step_id": "resolve-dut-package",
                    "kind": "identify_missing_evidence",
                    "status": "proposed",
                }
            ],
            "missingInfo": ["Verify the exact DUT package and pinout before fabrication."],
        }
    )
    return final


def _audit(initial: dict, *calls: dict) -> dict:
    return audit_codex_mission_progress(
        {"output": list(calls)},
        expected_project_id=PROJECT_ID,
        initial_snapshot=initial,
    )


def test_realistic_progression_passes_without_claiming_architecture_correctness() -> None:
    initial = spi_flash_adapter_snapshot()
    final = _progress_snapshot(initial)
    result = _audit(initial, _save(initial), _plan(), _read(final))

    assert result["schema_version"] == "hardware_splicer.codex_mission_progress_audit.v3"
    assert result["contract_pass"] is True
    assert result["checks"]["state_changed_beyond_project_identity"] is True
    assert result["checks"]["mission_output_surface_changed"] is True
    assert result["checks"]["state_producing_project_operation_succeeded"] is True
    assert result["state_producing_project_operations"][0]["reported_project_revision"] == 2
    assert result["checks"]["registered_source_records_preserved"] is True
    assert result["checks"]["initial_engineering_blockers_preserved"] is True
    assert result["checks"]["canonical_blocker_catalog_nonempty"] is True
    assert set(initial["engineeringBlockers"]).issubset(result["grounded_blocker_strings"])
    assert result["changed_mission_surfaces"] == [
        "engineeringPlan",
        "orderedSteps",
        "missingInfo",
    ]
    assert result["correct_engineering_architecture_asserted"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_blocker_catalog_uses_only_canonical_unresolved_surfaces() -> None:
    snapshot = spi_flash_adapter_snapshot()
    snapshot["missingInfo"] = ["Need exact pinout evidence."]
    snapshot["engineeringStatus"] = {
        "blockers": [{"blocker_id": "b1", "message": "Resolve supply implementation."}]
    }
    snapshot["engineeringAdvisories"].append("This advisory must not become a blocker.")
    catalog = canonical_blocker_catalog(snapshot)
    texts = {row["text"] for row in catalog}
    assert "Need exact pinout evidence." in texts
    assert "Resolve supply implementation." in texts
    assert set(snapshot["engineeringBlockers"]).issubset(texts)
    assert "This advisory must not become a blocker." not in texts


def test_noop_persist_and_readback_cannot_pass_as_mission_progress() -> None:
    initial = spi_flash_adapter_snapshot()
    result = _audit(initial, _save(initial), _read(initial, revision=1))

    assert result["contract_pass"] is False
    assert result["checks"]["final_canonical_readback_present"] is True
    assert result["checks"]["state_changed_beyond_project_identity"] is False
    assert result["checks"]["mission_output_surface_changed"] is False
    assert result["checks"]["state_producing_project_operation_succeeded"] is False


def test_project_identity_only_change_is_not_engineering_progress() -> None:
    initial = spi_flash_adapter_snapshot()
    final = copy.deepcopy(initial)
    final["projectId"] = PROJECT_ID
    result = _audit(initial, _save(final), _read(final, revision=1))

    assert result["contract_pass"] is False
    assert result["checks"]["state_changed_beyond_project_identity"] is False


def test_fabricated_progress_fields_via_generic_snapshot_save_are_insufficient() -> None:
    initial = spi_flash_adapter_snapshot()
    final = _progress_snapshot(initial)
    result = _audit(initial, _save(final), _read(final, revision=1))

    assert result["checks"]["state_changed_beyond_project_identity"] is True
    assert result["checks"]["mission_output_surface_changed"] is True
    assert result["checks"]["state_producing_project_operation_succeeded"] is False
    assert result["contract_pass"] is False


def test_operation_must_report_the_revision_that_is_finally_read_back() -> None:
    initial = spi_flash_adapter_snapshot()
    final = _progress_snapshot(initial)
    result = _audit(
        initial,
        _save(initial),
        _plan(reported_revision=2),
        _save(final, revision=3),
        _read(final, revision=3),
    )

    assert result["checks"]["mission_output_surface_changed"] is True
    assert result["final_project_revision"] == 3
    assert result["checks"]["state_producing_project_operation_succeeded"] is False
    assert result["state_producing_project_operations"] == []
    assert result["contract_pass"] is False


def test_substantive_operation_without_persisted_output_progress_is_insufficient() -> None:
    initial = spi_flash_adapter_snapshot()
    result = _audit(initial, _save(initial), _plan(), _read(initial))

    assert result["checks"]["state_producing_project_operation_succeeded"] is True
    assert result["checks"]["mission_output_surface_changed"] is False
    assert result["contract_pass"] is False


def test_registered_source_record_rewrite_blocks_progress_contract() -> None:
    initial = spi_flash_adapter_snapshot()
    final = _progress_snapshot(initial)
    final["engineeringSources"][0]["metadata"]["facts"]["host_logic_voltage_v"] = 5.0
    result = _audit(initial, _save(initial), _plan(), _read(final))

    assert result["checks"]["registered_source_ids_preserved"] is True
    assert result["checks"]["registered_source_records_preserved"] is False
    assert result["contract_pass"] is False


def test_registered_source_addition_or_removal_blocks_progress_contract() -> None:
    initial = spi_flash_adapter_snapshot()

    removed = _progress_snapshot(initial)
    removed["engineeringSources"] = removed["engineeringSources"][:-1]
    removed_result = _audit(initial, _save(initial), _plan(), _read(removed))
    assert removed_result["checks"]["registered_source_ids_preserved"] is False
    assert removed_result["contract_pass"] is False

    added = _progress_snapshot(initial)
    added["engineeringSources"].append(
        {
            "source_id": "invented-source",
            "content_hash": "sha256:invented",
            "revision": "1",
            "authority_ceiling": "declared",
            "metadata": {},
        }
    )
    added_result = _audit(initial, _save(initial), _plan(), _read(added))
    assert added_result["checks"]["registered_source_ids_preserved"] is False
    assert added_result["contract_pass"] is False


def test_initial_engineering_blocker_delete_or_rewrite_blocks_progress() -> None:
    initial = spi_flash_adapter_snapshot()

    deleted = _progress_snapshot(initial)
    deleted["engineeringBlockers"] = deleted["engineeringBlockers"][1:]
    deleted_result = _audit(initial, _save(initial), _plan(), _read(deleted))
    assert deleted_result["checks"]["initial_engineering_blockers_preserved"] is False
    assert deleted_result["contract_pass"] is False

    rewritten = _progress_snapshot(initial)
    rewritten["engineeringBlockers"][0] = "Resolved by model reasoning."
    rewritten_result = _audit(initial, _save(initial), _plan(), _read(rewritten))
    assert rewritten_result["checks"]["initial_engineering_blockers_preserved"] is False
    assert rewritten_result["contract_pass"] is False


def test_unresolved_identity_conflict_must_remain_unresolved() -> None:
    initial = next(
        dict(case.snapshot)
        for case in build_unseen_spi_flash_cases()
        if case.perturbation_kind == "conflicting_component_identity"
    )
    final = _progress_snapshot(initial)
    final["engineeringSourceConflicts"] = []
    result = _audit(initial, _save(initial), _plan(), _read(final))

    assert result["initial_unresolved_conflicts"]
    assert result["checks"]["initial_unresolved_conflicts_preserved"] is False
    assert result["contract_pass"] is False


def test_mission_or_constraints_rewrite_blocks_progress_contract() -> None:
    initial = spi_flash_adapter_snapshot()

    mission_rewrite = _progress_snapshot(initial)
    mission_rewrite["mission"] = "Different easier mission"
    mission_result = _audit(initial, _save(initial), _plan(), _read(mission_rewrite))
    assert mission_result["checks"]["persisted_mission_preserved"] is False
    assert mission_result["contract_pass"] is False

    constraint_rewrite = _progress_snapshot(initial)
    constraint_rewrite["constraints"]["authority_effect"] = "automatic"
    constraint_result = _audit(initial, _save(initial), _plan(), _read(constraint_rewrite))
    assert constraint_result["checks"]["persisted_constraints_preserved"] is False
    assert constraint_result["contract_pass"] is False


def test_final_snapshot_cannot_promote_readiness_or_authority() -> None:
    initial = spi_flash_adapter_snapshot()
    final = _progress_snapshot(initial)
    final["engineeringReadiness"] = {
        "fabrication_ready": True,
        "power_on_ready": False,
    }
    result = _audit(initial, _save(initial), _plan(), _read(final))

    assert result["checks"]["unsupported_final_truth_claims_absent"] is False
    assert any(
        row["path"].endswith("fabrication_ready")
        for row in result["unsupported_final_truth_claims"]
    )
    assert result["contract_pass"] is False


def test_readback_before_last_mutation_does_not_substantiate_final_state() -> None:
    initial = spi_flash_adapter_snapshot()
    final = _progress_snapshot(initial)
    result = _audit(initial, _save(initial), _read(final, revision=1), _plan())

    assert result["checks"]["state_producing_project_operation_succeeded"] is False
    assert result["checks"]["final_canonical_readback_present"] is False
    assert result["contract_pass"] is False


def test_unscoped_non_persistence_mutation_does_not_count_as_project_work() -> None:
    initial = spi_flash_adapter_snapshot()
    final = _progress_snapshot(initial)
    unrelated = _wrap_call(
        operation_id="hash_payload",
        method="POST",
        path="/v1/hashing/sha256",
        arguments={"operation_id": "hash_payload", "json_body": {"text": "x"}},
        body={"ok": True, "sha256": "0" * 64},
    )
    result = _audit(initial, _save(initial), unrelated, _read(final, revision=1))

    assert result["checks"]["state_producing_project_operation_succeeded"] is False
    assert result["contract_pass"] is False
