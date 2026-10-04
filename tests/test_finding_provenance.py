from __future__ import annotations

from copy import deepcopy

from hardware_splicer.ai_project_tool_executor import EXECUTABLE_AI_PREVIEW_ACTIONS
from hardware_splicer.engineering_review_identity import AUTHORITY_CEILING
from hardware_splicer.finding_provenance import project_findings
from hardware_splicer.machine_project import (
    AuthorityState,
    Domain,
    EvidenceRef,
    MachineProject,
    Requirement,
    RequirementKind,
    Subsystem,
)


def _machine_dump(**overrides) -> dict:
    project = MachineProject(
        project_id="fixture",
        name="Fixture",
        purpose="Provenance fixture.",
        requirements=[
            Requirement(
                requirement_id="req-open",
                statement="The rail shall stay within the declared current limit.",
                kind=RequirementKind.FUNCTIONAL,
                allocated_to=["rail"],
            )
        ],
        subsystems=[
            Subsystem(
                subsystem_id="rail",
                name="DUT rail",
                domain=Domain.ELECTRICAL,
                requirement_ids=["req-open"],
            ),
            Subsystem(
                subsystem_id="current-monitor",
                name="Current monitor",
                domain=Domain.ELECTRICAL,
            ),
            Subsystem(
                subsystem_id="test-equipment",
                name="Test equipment",
                domain=Domain.VERIFICATION,
            ),
        ],
        evidence=list(overrides.pop("evidence", [])),
        **overrides,
    )
    return project.model_dump(mode="json")


def _blocker_node(
    object_id: str,
    text: str,
    *,
    evidence_ids: list[str] | None = None,
) -> dict:
    row = {"object_id": object_id, "id": object_id, "blockers": [text]}
    if evidence_ids is not None:
        row["evidence_ids"] = evidence_ids
    return row


def _failed_action(
    action_id: str,
    action_type: str,
    message: str,
    *,
    tool_result: dict | None = ...,
    extra: dict | None = None,
) -> dict:
    action = {
        "action_id": action_id,
        "action_type": action_type,
        "title": message,
        "status": "failed",
        "automatic_execution": False,
    }
    if tool_result is ...:
        action["tool_result"] = {
            "status": "failed",
            "action_type": action_type,
            "error": {"type": "RuntimeError", "message": message},
            "summary": {"message": message},
        }
    else:
        action["tool_result"] = tool_result
    if extra:
        action.update(extra)
    return action


def _session(
    session_id: str,
    *,
    actions: list[dict] | None = None,
    provider: str | None = "mock",
    model: str | None = "fixture-v1",
    blockers: list[str] | None = None,
    open_questions: list[str] | None = None,
    risks: list[str] | None = None,
    turns: list[dict] | None = None,
    extra: dict | None = None,
) -> dict:
    session = {
        "session_id": session_id,
        "actions": list(actions or []),
    }
    if provider is not None:
        session["provider"] = provider
    if model is not None:
        session["model"] = model
    if blockers is not None:
        session["blockers"] = blockers
    if open_questions is not None:
        session["open_questions"] = open_questions
    if risks is not None:
        session["risks"] = risks
    if turns is not None:
        session["conversationTurns"] = turns
    if extra:
        session.update(extra)
    return session


def _by_text(findings: list[dict]) -> dict[str, dict]:
    return {row["text"]: row for row in findings}


def _kinds(findings: list[dict]) -> set[str]:
    return {row["provenance"]["kind"] for row in findings}


def test_snapshot_without_provenance_fields_is_unknown_never_deterministic() -> None:
    snapshot = {
        "engineeringSystemGraph": {
            "nodes": [_blocker_node("rail", "No measured startup-current evidence exists.")]
        },
        "engineeringAiSessions": [
            _session(
                "session-bare",
                provider=None,
                model=None,
                actions=[
                    _failed_action(
                        "action-unimplemented",
                        "invented_preview",
                        "Preview could not run.",
                    )
                ],
            )
        ],
    }

    findings = project_findings(snapshot, 1)

    assert findings
    assert _kinds(findings) == {"unknown"}
    assert "deterministic" not in _kinds(findings)
    assert "physical" not in _kinds(findings)
    for row in findings:
        assert row["provenance"]["authority_ceiling"] == AUTHORITY_CEILING == "observed"


def test_failed_check_deterministic_only_for_executor_registry() -> None:
    implemented = EXECUTABLE_AI_PREVIEW_ACTIONS[0]
    snapshot = {
        "engineeringAiSessions": [
            _session(
                "session-exec",
                actions=[
                    _failed_action(
                        "action-compose",
                        implemented,
                        "1.8 V DUT interface is not protected from 3.3 V controller",
                    ),
                    _failed_action(
                        "action-unknown-tool",
                        "run_erc",
                        "ERC adapter is not implemented.",
                    ),
                ],
            )
        ]
    }

    findings = project_findings(snapshot, 3)
    by_id = {row["provenance"]["source_ref"]: row for row in findings}

    assert by_id["action-compose"]["category"] == "failed_check"
    assert by_id["action-compose"]["provenance"]["kind"] == "deterministic"
    assert by_id["action-unknown-tool"]["provenance"]["kind"] == "unknown"


def test_failed_check_executable_type_requires_tool_result_for_deterministic() -> None:
    implemented = EXECUTABLE_AI_PREVIEW_ACTIONS[0]
    snapshot = {
        "engineeringAiSessions": [
            _session(
                "session-exec",
                actions=[
                    _failed_action(
                        "action-executed",
                        implemented,
                        "Compose preview failed after execution.",
                    ),
                    _failed_action(
                        "action-unexecuted",
                        implemented,
                        "Compose was proposed but never executed.",
                        tool_result=None,
                    ),
                    _failed_action(
                        "action-unknown-type",
                        "invented_preview",
                        "Unknown tool failed.",
                    ),
                ],
            )
        ]
    }

    findings = project_findings(snapshot, 1)
    by_id = {row["provenance"]["source_ref"]: row for row in findings}
    assert by_id["action-executed"]["provenance"]["kind"] == "deterministic"
    assert by_id["action-unexecuted"]["provenance"]["kind"] == "model_derived"
    assert by_id["action-unknown-type"]["provenance"]["kind"] == "unknown"


def test_failed_check_type_and_tool_must_agree() -> None:
    implemented = EXECUTABLE_AI_PREVIEW_ACTIONS[0]
    snapshot = {
        "engineeringAiSessions": [
            _session(
                "session-types",
                actions=[
                    {
                        "action_id": "action-agree",
                        "action_type": implemented,
                        "tool": implemented,
                        "title": "Agreeing fields.",
                        "status": "failed",
                        "tool_result": {
                            "status": "failed",
                            "action_type": implemented,
                            "tool": implemented,
                            "error": {"message": "Agreeing fields."},
                        },
                    },
                    {
                        "action_id": "action-type-unimplemented",
                        "action_type": "invented_preview",
                        "tool": implemented,
                        "title": "Type unimplemented, tool implemented.",
                        "status": "failed",
                        "tool_result": {
                            "status": "failed",
                            "error": {"message": "Type unimplemented, tool implemented."},
                        },
                    },
                    {
                        "action_id": "action-tool-unimplemented",
                        "action_type": implemented,
                        "tool": "invented_preview",
                        "title": "Type implemented, tool unimplemented.",
                        "status": "failed",
                        "tool_result": {
                            "status": "failed",
                            "error": {"message": "Type implemented, tool unimplemented."},
                        },
                    },
                    {
                        "action_id": "action-type-only",
                        "action_type": implemented,
                        "title": "Only action_type recorded.",
                        "status": "failed",
                        "tool_result": {
                            "status": "failed",
                            "error": {"message": "Only action_type recorded."},
                        },
                    },
                    {
                        "action_id": "action-tool-only",
                        "tool": implemented,
                        "title": "Only tool recorded.",
                        "status": "failed",
                        "tool_result": {
                            "status": "failed",
                            "error": {"message": "Only tool recorded."},
                        },
                    },
                ],
            )
        ]
    }

    findings = project_findings(snapshot, 1)
    by_id = {row["provenance"]["source_ref"]: row for row in findings}
    assert by_id["action-agree"]["provenance"]["kind"] == "deterministic"
    assert by_id["action-type-unimplemented"]["provenance"]["kind"] == "unknown"
    assert by_id["action-type-unimplemented"]["provenance"]["basis"] == (
        "recorded action_type/tool fields disagree"
    )
    assert by_id["action-tool-unimplemented"]["provenance"]["kind"] == "unknown"
    assert by_id["action-tool-unimplemented"]["provenance"]["basis"] == (
        "recorded action_type/tool fields disagree"
    )
    assert by_id["action-type-only"]["provenance"]["kind"] == "deterministic"
    assert by_id["action-tool-only"]["provenance"]["kind"] == "deterministic"


def test_failed_check_model_derived_when_proposal_never_executed() -> None:
    snapshot = {
        "engineeringAiSessions": [
            _session(
                "session-model",
                actions=[
                    _failed_action(
                        "action-propose",
                        "propose_architecture",
                        "Architecture proposal could not be completed.",
                        tool_result=None,
                    )
                ],
            )
        ]
    }

    findings = project_findings(snapshot, 1)
    assert len(findings) == 1
    assert findings[0]["category"] == "failed_check"
    assert findings[0]["provenance"]["kind"] == "model_derived"
    assert findings[0]["provenance"]["source_ref"] == "action-propose"


def test_object_blocker_model_derived_uses_session_id() -> None:
    text = "No powered-off high-impedance translator is proven."
    snapshot = {
        "engineeringSystemGraph": {"nodes": [_blocker_node("level-translation", text)]},
        "engineeringAiSessions": [
            _session(
                "outsider-session",
                provider="mock",
                model="outsider-fixture-v1",
                blockers=[text],
                open_questions=["Which powered-off-safe translator will be used?"],
            )
        ],
    }

    findings = project_findings(snapshot, 6)
    row = _by_text(findings)[text]
    assert row["category"] == "object_blocker"
    assert row["object_id"] == "level-translation"
    assert row["provenance"]["kind"] == "model_derived"
    assert row["provenance"]["source_ref"] == "outsider-session"


def test_object_blocker_model_derived_requires_provider_and_model() -> None:
    text = "Reserved-pin no-connect check has not passed."
    snapshot = {
        "engineeringSystemGraph": {"nodes": [_blocker_node("dut-socket", text)]},
        "engineeringAiSessions": [
            _session(
                "session-no-model",
                provider="mock",
                model=None,
                blockers=[text],
            )
        ],
    }

    findings = project_findings(snapshot, 1)
    assert _by_text(findings)[text]["provenance"]["kind"] == "unknown"
    assert _by_text(findings)[text]["provenance"]["source_ref"] is None


def test_object_blocker_citing_real_evidence_is_not_physical() -> None:
    unknown_text = "Measurement chain has no physical calibration evidence."
    model_text = "No powered-off high-impedance translator is proven."
    human_text = "Reset-time pull-up behavior crosses the DUT boundary."
    evidence = [
        EvidenceRef(
            evidence_id="evidence-bench",
            kind="bench_test",
            basis="instrument",
            supports=["current-monitor"],
            authority=AuthorityState.MEASURED,
            simulated=False,
        )
    ]
    snapshot = {
        "engineeringSystemGraph": {
            "nodes": [
                _blocker_node("current-monitor", unknown_text, evidence_ids=["evidence-bench"]),
                _blocker_node("level-translation", model_text, evidence_ids=["evidence-bench"]),
                _blocker_node("fixture-controller", human_text, evidence_ids=["evidence-bench"]),
            ]
        },
        "engineeringAiSessions": [
            _session("outsider-session", blockers=[model_text]),
            _session(
                "session-review",
                actions=[
                    {
                        "action_id": "action-reviewed",
                        "action_type": "prepare_verification",
                        "status": "accepted",
                        "decision": {
                            "decision": "accepted",
                            "reviewer": "fixture-reviewer",
                            "note": human_text,
                        },
                    }
                ],
            ),
        ],
        "machineProject": _machine_dump(evidence=evidence),
    }

    findings = project_findings(snapshot, 2)
    by_text = _by_text(findings)
    assert by_text[unknown_text]["provenance"]["kind"] == "unknown"
    assert by_text[model_text]["provenance"]["kind"] == "model_derived"
    assert by_text[human_text]["provenance"]["kind"] == "human"
    assert "physical" not in _kinds(findings)


def test_object_blocker_human_when_review_decision_carries_text() -> None:
    text = "Reset-time pull-up behavior crosses the DUT boundary."
    snapshot = {
        "engineeringSystemGraph": {"nodes": [_blocker_node("fixture-controller", text)]},
        "engineeringAiSessions": [
            _session(
                "session-review",
                actions=[
                    {
                        "action_id": "action-reviewed",
                        "action_type": "prepare_verification",
                        "status": "accepted",
                        "decision": {
                            "decision": "accepted",
                            "reviewer": "fixture-reviewer",
                            "note": text,
                        },
                    }
                ],
            )
        ],
    }

    findings = project_findings(snapshot, 1)
    row = _by_text(findings)[text]
    assert row["provenance"]["kind"] == "human"
    assert row["provenance"]["source_ref"] == "action-reviewed"


def test_traceability_issues_are_deterministic_regardless_of_evidence_basis() -> None:
    fixtures = [
        _machine_dump(
            evidence=[
                EvidenceRef(
                    evidence_id="evidence-obs",
                    kind="bench_test",
                    basis="observation",
                    supports=["req-open"],
                    authority=AuthorityState.OBSERVED,
                    simulated=False,
                )
            ]
        ),
        _machine_dump(
            evidence=[
                EvidenceRef(
                    evidence_id="evidence-instrument",
                    kind="bench_test",
                    basis="instrument",
                    supports=["req-open"],
                    authority=AuthorityState.MEASURED,
                    simulated=False,
                )
            ]
        ),
        _machine_dump(
            evidence=[
                EvidenceRef(
                    evidence_id="evidence-note",
                    kind="note",
                    basis="freeform_reviewer_comment",
                    supports=["req-open"],
                    authority=AuthorityState.UNKNOWN,
                    simulated=False,
                )
            ]
        ),
    ]

    for machine in fixtures:
        findings = [
            row
            for row in project_findings({"machineProject": machine}, 1)
            if row["category"] == "traceability_issue"
        ]
        assert findings
        for row in findings:
            assert row["provenance"]["kind"] == "deterministic"
            assert row["provenance"]["source_ref"] == "unverified_requirement"
            assert row["provenance"]["basis"] == (
                "computed by traceability_issues() over the stored machine project"
            )
        assert "physical" not in _kinds(findings)


def _duplicate_id_machine() -> dict:
    return {
        "project_id": "fixture",
        "name": "Fixture",
        "purpose": "Duplicate identifier.",
        "requirements": [
            {
                "requirement_id": "dup-id",
                "statement": "First use of the identifier.",
                "kind": "functional",
            },
            {
                "requirement_id": "dup-id",
                "statement": "Second use of the identifier.",
                "kind": "functional",
            },
        ],
    }


def _invalid_ref_machine() -> dict:
    return {
        "project_id": "fixture",
        "name": "Fixture",
        "purpose": "Unknown allocation.",
        "requirements": [
            {
                "requirement_id": "req-open",
                "statement": "Allocated to a missing object.",
                "kind": "functional",
                "allocated_to": ["missing-object"],
            }
        ],
    }


def _validation_findings(snapshot: dict) -> list[dict]:
    return [
        row
        for row in project_findings(snapshot, 1)
        if row["category"] == "traceability_issue"
        and row["provenance"]["source_ref"] == "machine_project_invalid"
    ]


def test_invalid_machine_project_duplicate_id_emits_validation_finding() -> None:
    findings = _validation_findings({"machineProject": _duplicate_id_machine()})
    assert len(findings) == 1
    row = findings[0]
    assert row["object_id"] is None
    assert row["provenance"]["kind"] == "deterministic"
    assert row["provenance"]["source_ref"] == "machine_project_invalid"
    assert row["provenance"]["basis"] == (
        "MachineProject validation rejected the stored machine project"
    )
    assert row["text"].startswith("Stored machine project fails validation: ")
    assert "dup-id" in row["text"]
    assert "pydantic.dev" not in row["text"]


def test_invalid_machine_project_invalid_ref_emits_validation_finding() -> None:
    findings = _validation_findings({"machine_project": _invalid_ref_machine()})
    assert len(findings) == 1
    row = findings[0]
    assert row["provenance"]["kind"] == "deterministic"
    assert row["provenance"]["source_ref"] == "machine_project_invalid"
    assert row["text"].startswith("Stored machine project fails validation: ")
    assert "missing-object" in row["text"]


def test_valid_machine_project_has_no_validation_finding() -> None:
    findings = _validation_findings({"machineProject": _machine_dump()})
    assert findings == []


def test_absent_or_empty_machine_project_has_no_validation_finding() -> None:
    assert _validation_findings({}) == []
    assert _validation_findings({"machineProject": {}}) == []
    assert _validation_findings({"machine_project": {}}) == []


def test_physical_kind_never_appears() -> None:
    snapshot = {
        "engineeringSystemGraph": {
            "nodes": [
                _blocker_node(
                    "current-monitor",
                    "Measurement chain has no physical calibration evidence.",
                    evidence_ids=["evidence-bench"],
                )
            ]
        },
        "engineeringAiSessions": [
            _session(
                "session-exec",
                actions=[_failed_action("action-compose", "run_compose", "Compose failed.")],
            )
        ],
        "machineProject": _machine_dump(
            evidence=[
                EvidenceRef(
                    evidence_id="evidence-bench",
                    kind="bench_test",
                    basis="instrument",
                    supports=["current-monitor"],
                    authority=AuthorityState.MEASURED,
                    simulated=False,
                )
            ]
        ),
    }
    findings = project_findings(snapshot, 1)
    assert findings
    assert "physical" not in _kinds(findings)


def test_finding_id_is_stable_across_calls_and_key_order() -> None:
    first = {
        "engineeringSystemGraph": {
            "nodes": [_blocker_node("rail", "No measured startup-current evidence exists.")]
        }
    }
    second = {
        "engineeringSystemGraph": {
            "nodes": [
                {
                    "blockers": ["No measured startup-current evidence exists."],
                    "id": "rail",
                    "object_id": "rail",
                }
            ]
        }
    }

    a = project_findings(first, 1)
    b = project_findings(first, 1)
    c = project_findings(second, 1)

    assert a == b
    assert a[0]["finding_id"] == c[0]["finding_id"]
    assert a[0]["finding_id"].startswith("finding-")
    assert len(a[0]["finding_id"]) == len("finding-") + 16


def test_dedupe_keeps_first_source_ref() -> None:
    text = "Exact translator part and powered-off behavior remain unverified."
    snapshot = {
        "engineeringSystemGraph": {
            "nodes": [
                _blocker_node("level-translation", text),
                _blocker_node("level-translation", text),
            ]
        },
        "engineeringAiSessions": [
            _session("session-a", blockers=[text]),
            _session("session-b", blockers=[text]),
        ],
    }

    findings = [
        row
        for row in project_findings(snapshot, 1)
        if row["category"] == "object_blocker" and row["text"] == text
    ]
    assert len(findings) == 1
    assert findings[0]["provenance"]["source_ref"] == "session-a"


def test_deterministic_category_object_text_order() -> None:
    snapshot = {
        "engineeringSystemGraph": {
            "nodes": [
                _blocker_node("z-object", "Later blocker."),
                _blocker_node("a-object", "Earlier blocker."),
            ]
        },
        "engineeringAiSessions": [
            _session(
                "session-order",
                actions=[
                    _failed_action("action-z", "run_compose", "Z failed."),
                    _failed_action("action-a", "run_compose", "A failed."),
                ],
            )
        ],
        "machineProject": _machine_dump(),
    }

    findings = project_findings(snapshot, 1)
    categories = [row["category"] for row in findings]
    assert categories == sorted(
        categories,
        key=lambda category: ["failed_check", "object_blocker", "traceability_issue"].index(
            category
        ),
    )
    failed = [row for row in findings if row["category"] == "failed_check"]
    blockers = [row for row in findings if row["category"] == "object_blocker"]
    assert [row["text"] for row in failed] == ["A failed.", "Z failed."]
    assert [(row["object_id"], row["text"]) for row in blockers] == [
        ("a-object", "Earlier blocker."),
        ("z-object", "Later blocker."),
    ]


def test_authority_ceiling_is_always_observed() -> None:
    snapshot = {
        "engineeringAiSessions": [
            _session(
                "session-exec",
                actions=[_failed_action("action-compose", "run_compose", "Compose failed.")],
            )
        ]
    }
    for row in project_findings(snapshot, 1):
        assert row["provenance"]["authority_ceiling"] == "observed"


def test_project_findings_does_not_mutate_input() -> None:
    snapshot = {
        "engineeringSystemGraph": {
            "nodes": [_blocker_node("rail", "No measured startup-current evidence exists.")]
        },
        "engineeringAiSessions": [
            _session(
                "session-exec",
                actions=[_failed_action("action-compose", "run_compose", "Compose failed.")],
            )
        ],
    }
    original = deepcopy(snapshot)
    project_findings(snapshot, 4)
    assert snapshot == original
