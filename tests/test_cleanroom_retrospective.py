from __future__ import annotations

import json

from hardware_splicer.cleanroom_replay import ReplayCase, run_cleanroom_replay
from hardware_splicer.cleanroom_retrospective import build_cleanroom_retrospective


def _snapshot(name: str = "Fixture A", source_id: str = "src-a", blocker: bool = False) -> dict:
    body = {
        "name": name,
        "mission": "Determine the next defensible engineering action from persisted evidence.",
        "engineeringSources": [{
            "source_id": source_id,
            "content_hash": f"sha256:{source_id}",
            "source_type": "engineering_source_json",
            "authority_ceiling": "declared",
        }],
    }
    if blocker:
        body["engineeringBlockers"] = ["Interface voltage remains unverified."]
    return body


def _response(action_type: str = "identify_missing_evidence", source_id: str = "src-a", questions=None, candidate: bool = False) -> dict:
    return {
        "summary": "The project remains proposal-only and depends on the persisted evidence.",
        "requirements": [{
            "id": "req-1",
            "statement": "Use only supported interface evidence.",
            "source_ids": [source_id],
            "assumptions": [],
        }],
        "open_questions": list(questions or []),
        "architecture_candidates": ([{
            "id": "candidate-1",
            "title": "Candidate interface architecture",
            "summary": "Proposal only.",
            "tradeoffs": [],
            "source_ids": [source_id],
        }] if candidate else []),
        "actions": [{
            "action_type": action_type,
            "title": "Resolve the next engineering step",
            "rationale": "Stay inside the visible evidence boundary.",
            "inputs": {},
            "source_ids": [source_id],
        }],
    }


def _llm(factory):
    def fake_llm(prompt: str, **kwargs: object) -> dict:
        return {
            "ok": True,
            "provider": "retrospective-test",
            "model": "deterministic",
            "content": json.dumps(factory(prompt)),
            "usage": {},
        }
    return fake_llm


def test_label_drift_maps_to_script_brain_signal() -> None:
    cases = [
        ReplayCase("a", "project-a", 1, _snapshot("Fixture A"), "label-equivalent", "baseline"),
        ReplayCase("b", "project-b", 1, _snapshot("Fixture B"), "label-equivalent", "renamed_fixture"),
    ]
    report = run_cleanroom_replay(
        cases,
        llm_callable=_llm(lambda prompt: _response(
            action_type="clarify_requirement" if "Fixture A" in prompt else "identify_missing_evidence"
        )),
    )
    retrospective = build_cleanroom_retrospective(report, cases=cases)
    diagnosis = retrospective["group_diagnoses"][0]
    assert diagnosis["primary_class"] == "SCRIPT_BRAIN"
    assert retrospective["correct_architecture_asserted"] is False


def test_changed_evidence_invalidates_equivalence_claim() -> None:
    cases = [
        ReplayCase("a", "project-a", 1, _snapshot(source_id="src-a"), "bad-equivalence", "baseline"),
        ReplayCase("b", "project-b", 1, _snapshot(source_id="src-b"), "bad-equivalence", "renamed_fixture"),
    ]
    report = run_cleanroom_replay(
        cases,
        llm_callable=_llm(lambda prompt: _response(source_id="src-b" if "src-b" in prompt else "src-a")),
    )
    assert report["equivalence_groups"]["bad-equivalence"]["invalid_equivalence_claim"] is True
    retrospective = build_cleanroom_retrospective(report, cases=cases)
    assert retrospective["group_diagnoses"][0]["primary_class"] == "TEST_ORACLE"
    assert retrospective["failure_taxonomy_counts"].get("SCRIPT_BRAIN", 0) == 0


def test_blocker_without_question_is_uncertainty_failure() -> None:
    cases = [ReplayCase("blocked", "project-a", 1, _snapshot(blocker=True))]
    report = run_cleanroom_replay(
        cases,
        llm_callable=_llm(lambda prompt: _response(candidate=True)),
    )
    retrospective = build_cleanroom_retrospective(report, cases=cases)
    assessment = retrospective["case_assessments"][0]
    signals = {row.get("signal") for row in assessment["diagnoses"]}
    assert "underexpressed_uncertainty" in signals
    assert "forced_guess_suspected" in signals
    assert assessment["operator_retrospective"]["forced_to_guess_suspected"] is True
    assert retrospective["metrics"]["agentic_competence"]["clarification_discipline_rate"] == 0.0
