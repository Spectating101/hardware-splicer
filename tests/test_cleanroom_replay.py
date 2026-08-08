from __future__ import annotations

import json

from hardware_splicer.cleanroom_replay import ReplayCase, run_cleanroom_replay


def _snapshot(name: str = "Fixture Alpha") -> dict:
    return {
        "name": name,
        "mission": "Determine the next defensible engineering action from the available evidence.",
        "constraints": {"max_voltage_v": 3.3},
        "engineeringSources": [
            {
                "source_id": "src-b",
                "source_type": "engineering_source_json",
                "content_hash": "sha256:b",
                "authority_ceiling": "declared",
                "metadata": {"label": "second source"},
            },
            {
                "source_id": "src-a",
                "source_type": "engineering_source_json",
                "content_hash": "sha256:a",
                "authority_ceiling": "declared",
                "metadata": {"label": "first source"},
            },
        ],
        "engineeringBlockers": ["interface voltage is not independently verified"],
    }


def _response(action_type: str = "identify_missing_evidence", source_id: str = "src-a") -> dict:
    return {
        "summary": "Keep the interface blocked until the missing evidence is resolved.",
        "requirements": [
            {
                "id": "req-1",
                "statement": "Respect the declared voltage ceiling.",
                "source_ids": [source_id],
                "assumptions": [],
            }
        ],
        "open_questions": ["What is independently measured at the unresolved interface?"],
        "architecture_candidates": [],
        "actions": [
            {
                "action_type": action_type,
                "title": "Resolve the interface evidence",
                "rationale": "The persisted evidence is incomplete.",
                "inputs": {},
                "source_ids": [source_id],
            }
        ],
    }


def test_source_order_variants_are_structurally_stable_without_golden_answer() -> None:
    base = _snapshot()
    reversed_snapshot = {**base, "engineeringSources": list(reversed(base["engineeringSources"]))}

    def fake_llm(prompt: str, **kwargs: object) -> dict:
        return {
            "ok": True,
            "provider": "replay-test",
            "model": "deterministic",
            "content": json.dumps(_response()),
            "usage": {},
        }

    report = run_cleanroom_replay(
        [
            ReplayCase("base", "project-a", 1, base, "order-equivalent", "baseline"),
            ReplayCase(
                "reversed",
                "project-a",
                2,
                reversed_snapshot,
                "order-equivalent",
                "source_order_reverse",
            ),
        ],
        llm_callable=fake_llm,
    )

    assert report["golden_answer_used"] is False
    assert report["correct_architecture_asserted"] is False
    assert report["hard_failure_count"] == 0
    comparison = report["equivalence_groups"]["order-equivalent"]
    assert comparison["comparable"] is True
    assert comparison["structural_drift"] is False
    assert comparison["drift_fields"] == []


def test_renamed_fixture_drift_is_reported_not_declared_wrong() -> None:
    alpha = _snapshot("Fixture Alpha")
    beta = _snapshot("Fixture Beta")

    def label_sensitive_llm(prompt: str, **kwargs: object) -> dict:
        action_type = "clarify_requirement" if "Fixture Alpha" in prompt else "identify_missing_evidence"
        return {
            "ok": True,
            "provider": "replay-test",
            "model": "label-sensitive",
            "content": json.dumps(_response(action_type=action_type)),
            "usage": {},
        }

    report = run_cleanroom_replay(
        [
            ReplayCase("alpha", "project-a", 1, alpha, "rename-equivalent", "baseline"),
            ReplayCase("beta", "project-b", 1, beta, "rename-equivalent", "renamed_fixture"),
        ],
        llm_callable=label_sensitive_llm,
    )

    comparison = report["equivalence_groups"]["rename-equivalent"]
    assert comparison["structural_drift"] is True
    assert "action_types" in comparison["drift_fields"]
    signals = [
        row
        for row in report["retrospective_signals"]
        if row.get("equivalence_group") == "rename-equivalent"
    ]
    assert signals
    assert signals[0]["suggested_review_class"] == "possible_label_or_script_brain_coupling"
    assert report["correct_architecture_asserted"] is False


def test_invented_evidence_identity_becomes_hard_cleanroom_failure() -> None:
    def hallucinating_llm(prompt: str, **kwargs: object) -> dict:
        return {
            "ok": True,
            "provider": "replay-test",
            "model": "hallucinating",
            "content": json.dumps(_response(source_id="invented-source")),
            "usage": {},
        }

    report = run_cleanroom_replay(
        [ReplayCase("invented-evidence", "project-a", 1, _snapshot())],
        llm_callable=hallucinating_llm,
    )

    assert report["hard_failure_count"] == 1
    row = report["results"][0]
    assert row["ok"] is False
    assert row["failure_class"] == "cleanroom_contract"
    assert "invented product evidence identities" in row["error"]


def test_provider_failure_is_recorded_separately_from_contract_failure() -> None:
    def failed_provider(prompt: str, **kwargs: object) -> dict:
        return {
            "ok": False,
            "provider": "replay-test",
            "error": "provider_unavailable",
        }

    report = run_cleanroom_replay(
        [ReplayCase("provider-failure", "project-a", 1, _snapshot())],
        llm_callable=failed_provider,
    )

    assert report["hard_failure_count"] == 1
    row = report["results"][0]
    assert row["failure_class"] == "provider_or_runtime"
    assert row["ok"] is False
