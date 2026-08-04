from __future__ import annotations

import pytest

from hardware_splicer.engineering_execution_anchored_api import _anchored_base_plan
from hardware_splicer.engineering_plan_store import save_engineering_plan
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore, RevisionConflict


def _plan(*, marker: str) -> dict:
    return {
        "machine_project": {
            "project_id": "execution-anchor",
            "name": "Execution anchor",
            "purpose": "Ensure execution evidence cannot replace stored state.",
        },
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"topology_id": "generic", "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
        "retained_marker": marker,
        "audited_physical_evidence": {
            "applicable": False,
            "blockers": ["Retained audit marker"],
            "envelopes": [{"envelope_id": "retained-envelope"}],
            "ledger_entries": [{"entry_id": "retained-entry"}],
        },
    }


def test_canonical_product_uses_anchored_execution_save_endpoint(tmp_path) -> None:
    app = create_product_app(ProjectStore(tmp_path / "projects"))
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", None)
        == "/v1/engineering/execution/evidence/save"
    ]

    assert len(routes) == 1
    assert routes[0].endpoint.__module__ == (
        "hardware_splicer.engineering_execution_anchored_api"
    )


def test_existing_execution_save_resolves_stored_plan_not_caller_plan(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    save_engineering_plan(
        store,
        _plan(marker="stored"),
        expected_revision=0,
    )

    base, project_id, source = _anchored_base_plan(
        store,
        _plan(marker="caller replacement"),
        project_id=None,
        expected_revision=1,
    )

    assert project_id == "execution-anchor"
    assert source == "stored_revision"
    assert base["retained_marker"] == "stored"
    assert base["audited_physical_evidence"]["envelopes"][0]["envelope_id"] == "retained-envelope"


def test_execution_save_requires_explicit_latest_revision(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    save_engineering_plan(
        store,
        _plan(marker="stored"),
        expected_revision=0,
    )

    with pytest.raises(RevisionConflict, match="expected_revision is required"):
        _anchored_base_plan(
            store,
            _plan(marker="caller"),
            project_id=None,
            expected_revision=None,
        )

    with pytest.raises(RevisionConflict, match="is at revision 1, expected 0"):
        _anchored_base_plan(
            store,
            _plan(marker="caller"),
            project_id=None,
            expected_revision=0,
        )
