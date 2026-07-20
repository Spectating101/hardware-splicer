from __future__ import annotations

from hardware_splicer.machine_project import (
    AuthorityState,
    EvidenceRef,
    MachineProject,
    ReleaseState,
)
from hardware_splicer.machine_project_diff import diff_machine_projects


def machine(*, release: ReleaseState, include_evidence: bool) -> MachineProject:
    return MachineProject(
        project_id="review-machine",
        name="Review machine",
        purpose="Exercise semantic review gates.",
        requested_release_state=release,
        evidence=(
            [
                EvidenceRef(
                    evidence_id="evidence-power",
                    kind="bench_measurement",
                    basis="instrument",
                    supports=["review-machine"],
                    authority=AuthorityState.MEASURED,
                )
            ]
            if include_evidence
            else []
        ),
    )


def test_release_target_change_requires_review() -> None:
    base = machine(release=ReleaseState.DESIGN_READY, include_evidence=True)
    candidate = machine(release=ReleaseState.OPERATIONALLY_AUTHORIZED, include_evidence=True)

    diff = diff_machine_projects(base, candidate)

    assert {flag.code for flag in diff.review_flags} == {
        "requested_release_state_changed"
    }
    assert diff.review_required is True


def test_evidence_removal_requires_review() -> None:
    base = machine(release=ReleaseState.DESIGN_READY, include_evidence=True)
    candidate = machine(release=ReleaseState.DESIGN_READY, include_evidence=False)

    diff = diff_machine_projects(base, candidate)
    evidence_change = next(
        change
        for change in diff.object_changes
        if change.collection == "evidence"
        and change.object_id == "evidence-power"
    )

    assert evidence_change.change_type.value == "removed"
    assert {flag.code for flag in evidence_change.review_flags} == {
        "evidence_removed"
    }
    assert evidence_change.review_required is True
