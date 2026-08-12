from __future__ import annotations

from hardware_splicer.cleanroom_perturbations import (
    build_conflicting_evidence_case,
    build_partial_evidence_case,
    build_standard_equivalence_suite,
    neutralize_display_labels,
    reverse_source_order,
)
from hardware_splicer.cleanroom_replay import ReplayCase


def _snapshot() -> dict:
    return {
        "name": "Named Fixture",
        "mission": "Determine the next defensible engineering action.",
        "constraints": {"logic_voltage_v": 1.8},
        "available_parts": [
            {
                "component_id": "cmp-1",
                "name": "Familiar Sensor Board",
                "type": "sensor_interface",
                "voltage_v": 1.8,
            }
        ],
        "engineeringSources": [
            {
                "source_id": "src-a",
                "content_hash": "sha256:a",
                "source_type": "engineering_source_json",
                "authority_ceiling": "declared",
                "metadata": {"label": "Alpha datasheet"},
            },
            {
                "source_id": "src-b",
                "content_hash": "sha256:b",
                "source_type": "engineering_source_json",
                "authority_ceiling": "declared",
                "metadata": {"label": "Beta measurement"},
            },
        ],
    }


def _identity(snapshot: dict) -> list[tuple[str, str]]:
    return sorted(
        (row["source_id"], row["content_hash"])
        for row in snapshot["engineeringSources"]
    )


def test_equivalent_order_and_label_perturbations_preserve_evidence_identity() -> None:
    baseline = _snapshot()
    reversed_snapshot = reverse_source_order(baseline)
    neutralized = neutralize_display_labels(baseline)

    assert _identity(reversed_snapshot) == _identity(baseline)
    assert _identity(neutralized) == _identity(baseline)
    assert reversed_snapshot["engineeringSources"][0]["source_id"] == "src-b"
    assert neutralized["name"] == "Neutral Project"
    assert neutralized["engineeringSources"][0]["metadata"]["label"] == "source-1"
    assert baseline["name"] == "Named Fixture"


def test_standard_suite_generates_controlled_equivalent_variants_without_answers() -> None:
    base_case = ReplayCase(
        "base",
        "project-a",
        3,
        _snapshot(),
    )
    cases = build_standard_equivalence_suite(
        base_case,
        mission_paraphrase_text="Using only persisted evidence, identify the next justified engineering step.",
        include_part_label_neutralization=True,
    )

    kinds = {case.perturbation_kind for case in cases}
    assert kinds == {
        "baseline",
        "source_order_reverse",
        "source_order_rotate",
        "neutralized_labels",
        "unfamiliar_equivalent_component",
        "mission_paraphrase",
    }
    assert len({case.equivalence_group for case in cases}) == 1
    assert all(case.metadata["equivalence_asserted_by"] == "outer_engineer" for case in cases)
    assert all("expected_architecture" not in (case.metadata or {}) for case in cases)


def test_partial_and_conflicting_evidence_are_challenges_not_equivalence_claims() -> None:
    base_case = ReplayCase("base", "project-a", 3, _snapshot(), "should-not-propagate")
    partial = build_partial_evidence_case(base_case, remove_source_ids=["src-b"])
    conflict = build_conflicting_evidence_case(
        base_case,
        conflict={
            "conflict_id": "conf-1",
            "source_ids": ["src-a", "src-b"],
            "reason": "Two declared sources disagree about interface voltage.",
        },
    )

    assert partial.equivalence_group is None
    assert partial.perturbation_kind == "partial_evidence"
    assert [row["source_id"] for row in partial.snapshot["engineeringSources"]] == ["src-a"]
    assert partial.metadata["expected_equivalent"] is False

    assert conflict.equivalence_group is None
    assert conflict.perturbation_kind == "conflicting_evidence"
    assert conflict.snapshot["declared_conflicts"][0]["conflict_id"] == "conf-1"
    assert conflict.metadata["expected_equivalent"] is False
