from __future__ import annotations

import hardware_splicer.change_impact as impact_module
import hardware_splicer.integrations.llm_policy as llm_policy
from hardware_splicer.change_impact import ImpactSeverity, build_change_impact_graph
from hardware_splicer.engineering_source_graph import (
    EngineeringSource,
    EngineeringSourceGraph,
    SourceType,
)
from hardware_splicer.semantic_impact_scope import (
    SemanticImpactScopeError,
    parse_impact_scope_proposal,
)


def _model_scope(*domains: str):
    return parse_impact_scope_proposal(
        {
            "status": "model_proposed",
            "domains": list(domains),
            "reasoning": "Bounded semantic test proposal.",
            "confidence": 0.6,
            "unresolved_questions": [],
            "source": "model_proposed",
            "authority_effect": "none",
            "automatic_execution": False,
        }
    )


def test_model_first_domains_ignore_trigger_keyword_ontology(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(impact_module, "interpret_impact_scope", lambda *args, **kwargs: _model_scope("firmware"))

    graph = build_change_impact_graph(
        {
            "mode": "greenfield",
            "goal": "battery arm ROS brownout wheel camera motor words are deliberately adversarial",
        }
    )

    assert graph.affected_domains == ["firmware", "system", "verification"]
    assert graph.metadata["impact_scope_source"] == "model_proposed"
    assert graph.metadata["impact_scope_status"] == "model_proposed"
    assert all(row.metadata["target_projection"] == "structural_domain_projection" for row in graph.impacts)
    assert all(row.severity == ImpactSeverity.REVIEW for row in graph.impacts)


def test_model_first_trigger_does_not_keyword_match_source_identity(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(impact_module, "interpret_impact_scope", lambda *args, **kwargs: _model_scope("electrical"))
    source_graph = EngineeringSourceGraph(
        sources=[
            EngineeringSource(
                source_id="src-battery",
                source_type=SourceType.DATASHEET,
                uri="docs/battery-brownout-notes.pdf",
            )
        ]
    )

    graph = build_change_impact_graph(
        {"mode": "greenfield", "goal": "battery brownout investigation"},
        source_graph=source_graph,
    )

    goal_trigger = next(row for row in graph.triggers if row.trigger_type == "goal")
    assert goal_trigger.source_ids == []
    assert goal_trigger.metadata["source_binding"] == "none"


def test_explicit_trigger_source_id_binds_without_text_matching(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(impact_module, "interpret_impact_scope", lambda *args, **kwargs: _model_scope("electrical"))
    source_graph = EngineeringSourceGraph(
        sources=[
            EngineeringSource(
                source_id="src-interface",
                source_type=SourceType.MEASUREMENT,
                uri="measurements/run-7.json",
            )
        ]
    )

    graph = build_change_impact_graph(
        {
            "mode": "modify",
            "baseline_revision": 4,
            "change_request": {
                "statement": "Re-evaluate the changed interface.",
                "source_ids": ["src-interface"],
                "evidence_ids": ["measurement-7"],
            },
        },
        source_graph=source_graph,
    )

    trigger = next(row for row in graph.triggers if row.trigger_type == "change_request")
    assert trigger.source_ids == ["src-interface"]
    assert trigger.evidence_ids == ["measurement-7"]
    assert trigger.metadata["source_binding"] == "declared"


def test_unresolved_semantic_scope_fails_closed_to_policy_domains(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)

    def fail_scope(*args, **kwargs):
        raise SemanticImpactScopeError("provider unavailable")

    monkeypatch.setattr(impact_module, "interpret_impact_scope", fail_scope)
    graph = build_change_impact_graph(
        {"mode": "greenfield", "goal": "The candidate behaves differently after revision."}
    )

    assert graph.affected_domains == ["system", "verification"]
    assert graph.metadata["impact_scope_status"] == "unresolved"
    assert graph.metadata["impact_scope_source"] == "unresolved"
    assert any(row.get("field") == "impact_scope" for row in graph.unresolved)


def test_non_greenfield_policy_additions_cannot_be_omitted_by_model(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(impact_module, "interpret_impact_scope", lambda *args, **kwargs: _model_scope("software"))

    graph = build_change_impact_graph(
        {
            "mode": "repair",
            "goal": "Repair behavior changes in the application layer.",
        }
    )

    assert set(graph.affected_domains) == {
        "system",
        "verification",
        "safety",
        "assembly",
        "electrical",
        "software",
    }
    safety = next(row for row in graph.impacts if row.domain.value == "safety")
    assert safety.severity == ImpactSeverity.SAFETY_CRITICAL
    assert "electrical" in graph.metadata["impact_scope_proposal"]["policy_added_domains"]
    assert any(row.get("field") == "baseline_revision" for row in graph.unresolved)
