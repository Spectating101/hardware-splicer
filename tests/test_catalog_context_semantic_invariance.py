from __future__ import annotations

from hardware_splicer.integrations.catalog_context import catalog_context_for_goal


def test_model_catalog_context_is_not_ranked_by_goal_keywords() -> None:
    motor = catalog_context_for_goal("four wheel rover motor drive", max_entries=200)
    sensor = catalog_context_for_goal("greenhouse humidity sensor", max_entries=200)
    unrelated = catalog_context_for_goal("completely unfamiliar project wording", max_entries=200)

    assert motor == sensor == unrelated
    assert motor


def test_paraphrasing_goal_cannot_change_visible_catalog_subset() -> None:
    first = catalog_context_for_goal(
        "I need the shaft to rotate in either direction under logic control.",
        max_entries=80,
    )
    second = catalog_context_for_goal(
        "Software should command positive or negative rotation of the same load.",
        max_entries=80,
    )

    assert first == second
