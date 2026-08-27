from __future__ import annotations

from dataclasses import replace

from hardware_splicer.cleanroom_conflict_audit import audit_conflict_source_coverage
from hardware_splicer.cleanroom_dut_experiment import build_dut_fixture_cases


def _conflict_case():
    return next(case for case in build_dut_fixture_cases() if case.perturbation_kind == "conflicting_evidence")


def _report(case_id: str, source_ids: list[str], *, ok: bool = True) -> dict:
    return {
        "results": [
            {
                "case_id": case_id,
                "ok": ok,
                "signature": {"referenced_source_ids": source_ids},
            }
        ]
    }


def test_conflict_coverage_passes_when_operator_references_both_sides() -> None:
    case = _conflict_case()
    report = _report(
        case.case_id,
        ["src-controller", "src-dut", "src-dut-conflict", "src-fixture"],
    )

    audit = audit_conflict_source_coverage(report, cases=[case])

    assert audit["status"] == "pass"
    assert audit["conflict_case_count"] == 1
    assert audit["conflict_source_coverage_rate"] == 1.0
    assert audit["findings"] == []


def test_conflict_coverage_reports_missing_side_as_evidence_model() -> None:
    case = _conflict_case()
    report = _report(case.case_id, ["src-controller", "src-dut", "src-fixture"])

    audit = audit_conflict_source_coverage(report, cases=[case])

    assert audit["status"] == "review"
    assert audit["conflict_source_coverage_rate"] == 0.0
    finding = audit["findings"][0]
    assert finding["primary_class"] == "EVIDENCE_MODEL"
    assert finding["signal"] == "conflict_source_undercoverage"
    assert finding["source_ids"] == ["src-dut-conflict"]


def test_invalid_conflict_source_is_test_oracle_not_model_failure() -> None:
    case = _conflict_case()
    snapshot = dict(case.snapshot)
    snapshot["engineeringSourceConflicts"] = [
        {
            "conflict_id": "bad-conflict",
            "source_ids": ["src-dut", "src-not-in-inventory"],
            "status": "unresolved",
        }
    ]
    snapshot["engineeringAnalysis"] = {}
    broken = replace(case, case_id="invalid-conflict", snapshot=snapshot)
    report = _report(broken.case_id, ["src-dut"])

    audit = audit_conflict_source_coverage(report, cases=[broken])

    assert audit["status"] == "review"
    finding = audit["findings"][0]
    assert finding["primary_class"] == "TEST_ORACLE"
    assert finding["signal"] == "conflict_references_absent_source"
    assert finding["source_ids"] == ["src-not-in-inventory"]
