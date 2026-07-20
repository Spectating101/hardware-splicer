"""Release-state ordering for canonical machine projects.

Release authority is monotonic: evidence supporting a higher state also satisfies
lower requested states. Blockers always win. Keep this policy separate from the
ontology so API, UI, and future CI gates share one ordering rule.
"""

from __future__ import annotations

from .machine_project import ReleaseAssessment, ReleaseState

_RELEASE_ORDER = {
    ReleaseState.CONCEPT: 0,
    ReleaseState.DESIGN_READY: 1,
    ReleaseState.BUILD_READY: 2,
    ReleaseState.BENCH_READY: 3,
    ReleaseState.OPERATIONALLY_AUTHORIZED: 4,
}


def release_state_satisfies(achieved: ReleaseState, requested: ReleaseState) -> bool:
    """Return true when achieved authority is at least the requested authority."""

    return _RELEASE_ORDER[achieved] >= _RELEASE_ORDER[requested]


def assessment_allows(assessment: ReleaseAssessment) -> bool:
    """Canonical permission rule for API/UI/CI release decisions."""

    return not assessment.blockers and release_state_satisfies(
        assessment.achieved_state,
        assessment.requested_state,
    )
