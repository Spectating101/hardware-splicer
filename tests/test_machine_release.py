from __future__ import annotations

from hardware_splicer.machine_project import ReleaseAssessment, ReleaseState, TraceabilityIssue
from hardware_splicer.machine_release import assessment_allows, release_state_satisfies


def assessment(
    achieved: ReleaseState,
    requested: ReleaseState,
    *,
    blocked: bool = False,
) -> ReleaseAssessment:
    return ReleaseAssessment(
        achieved_state=achieved,
        requested_state=requested,
        blockers=(
            [TraceabilityIssue(code="blocked", message="release is blocked")]
            if blocked
            else []
        ),
    )


def test_higher_release_state_satisfies_lower_requested_state() -> None:
    assert release_state_satisfies(
        ReleaseState.OPERATIONALLY_AUTHORIZED,
        ReleaseState.DESIGN_READY,
    ) is True
    assert assessment_allows(
        assessment(
            ReleaseState.OPERATIONALLY_AUTHORIZED,
            ReleaseState.DESIGN_READY,
        )
    ) is True


def test_lower_release_state_does_not_satisfy_higher_request() -> None:
    assert release_state_satisfies(
        ReleaseState.DESIGN_READY,
        ReleaseState.BENCH_READY,
    ) is False
    assert assessment_allows(
        assessment(ReleaseState.DESIGN_READY, ReleaseState.BENCH_READY)
    ) is False


def test_blockers_override_sufficient_release_state() -> None:
    assert assessment_allows(
        assessment(
            ReleaseState.OPERATIONALLY_AUTHORIZED,
            ReleaseState.BUILD_READY,
            blocked=True,
        )
    ) is False
