"""Engine benchmark: every brief's checks are known, coverage ranks missing features, and a project is scored."""
from __future__ import annotations

from hardware_splicer import engine_benchmark as eb
from hardware_splicer import engineering_toolbelt as tb


def test_every_brief_check_is_known_and_every_named_tool_exists():
    for b in eb.BRIEFS:
        assert set(b["checks"]) <= set(eb.CHECKS), b["id"]
    assert {t for t in eb.CHECKS.values() if t} <= set(tb.TOOLS)


def test_coverage_ranks_missing_features_and_scoring_reads_a_project(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_PROJECTS_ROOT", str(tmp_path))
    c = eb.coverage()
    assert 0 < c["overall_share"] < 1 and c["missing_features_by_need"][0][1] >= 2
    pid = tb.call("hs_project_open", {"objective": "underwater drone"})["result"]["project_id"]
    tb.call("hs_prior_art_search", {"project_id": pid, "query": "rov", "sources": ["hs_own"]})
    tb.call("hs_junk_lookup", {"project_id": pid, "needs": ["camera"]})
    tb.call("hs_project_record", {"project_id": pid, "kind": "note", "title": "gap: no buoyancy check"})
    s = eb.score(pid)
    assert s["prior_art"] and s["junk_plan"] and s["gaps_recorded"] == ["gap: no buoyancy check"] and s["score_of_6"] == 2.0
