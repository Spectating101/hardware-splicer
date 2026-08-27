from __future__ import annotations

import json

from hardware_splicer.cleanroom_replay import ReplayCase, run_cleanroom_replay
from hardware_splicer.cleanroom_retrospective import build_cleanroom_retrospective


def _snapshot(blocker: bool = False) -> dict:
    body = {
        "mission": "Determine the next defensible engineering action.",
        "engineeringSources": [{
            "source_id": "src-a",
            "content_hash": "sha256:a",
            "source_type": "engineering_source_json",
            "authority_ceiling": "declared",
        }],
    }
    if blocker:
        body["engineeringBlockers"] = ["Interface voltage remains unverified."]
    return body


def _response(source_id: str = "src-a", questions=None) -> dict:
    return {
        "summary": "Resolve uncertainty before stronger engineering claims.",
        "requirements": [{
            "id": "req-1",
            "statement": "Respect the visible source boundary.",
            "source_ids": [source_id],
            "assumptions": [],
        }],
        "open_questions": list(questions or []),
        "architecture_candidates": [],
        "actions": [{
            "action_type": "identify_missing_evidence",
            "title": "Resolve evidence gap",
            "rationale": "The current evidence is incomplete.",
            "inputs": {},
            "source_ids": [source_id],
        }],
    }


def _llm(payload: dict):
    def fake_llm(prompt: str, **kwargs: object) -> dict:
        return {
            "ok": True,
            "provider": "retrospective-test",
            "model": "deterministic",
            "content": json.dumps(payload),
            "usage": {},
        }
    return fake_llm


def test_clarification_is_preserved_in_operator_retrospective() -> None:
    cases = [ReplayCase("blocked", "project-a", 1, _snapshot(blocker=True))]
    report = run_cleanroom_replay(
        cases,
        llm_callable=_llm(_response(questions=["What voltage is independently measured at the interface?"])),
    )
    retrospective = build_cleanroom_retrospective(report, cases=cases)
    assert retrospective["metrics"]["agentic_competence"]["clarification_discipline_rate"] == 1.0
    assessment = retrospective["case_assessments"][0]
    assert assessment["operator_retrospective"]["information_unavailable"]
    assert assessment["operator_retrospective"]["forced_to_guess_suspected"] is False


def test_unknown_evidence_identity_maps_to_evidence_model() -> None:
    cases = [ReplayCase("bad-evidence", "project-a", 1, _snapshot())]
    report = run_cleanroom_replay(
        cases,
        llm_callable=_llm(_response(source_id="unknown-source")),
    )
    retrospective = build_cleanroom_retrospective(report, cases=cases)
    diagnosis = retrospective["case_assessments"][0]["diagnoses"][0]
    assert diagnosis["primary_class"] == "EVIDENCE_MODEL"
    assert diagnosis["confidence"] == "high"
    assert retrospective["metrics"]["truth"]["evidence_identity_contract_rate"] == 0.0
