"""Ranking hardware-data repositories by GitHub signals, and handing the result to the signal pipeline as discovered-only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from hardware_splicer.github_data_sources import feed, licence_class, rank, search
from hardware_splicer.github_signal_pipeline import normalize_feed

NOW = datetime(2026, 11, 25, tzinfo=timezone.utc)


def _repo(name, stars, pushed, spdx, archived=False):
    return {"full_name": name, "stargazers_count": stars, "pushed_at": pushed, "license": {"spdx_id": spdx} if spdx else None,
            "archived": archived, "description": "", "default_branch": "main"}


def test_licence_classes():
    assert licence_class("MIT") == licence_class("CC-BY-4.0") == "absorb"
    assert licence_class("GPL-3.0") == licence_class("CC-BY-SA-4.0") == licence_class("EPL-2.0") == "review_only"
    assert licence_class(None) == licence_class("NOASSERTION") == "unusable"


def test_ranking_weighs_reach_activity_licence_and_breadth():
    def fake(args):
        q = next(a for a in args if a.startswith("q="))[2:]
        items = [_repo("big/unlicensed", 50000, "2026-11-01T00:00:00Z", None), _repo("small/active", 300, "2026-11-01T00:00:00Z", "MIT"),
                 _repo("old/stale", 3000, "2022-01-01T00:00:00Z", "MIT")]
        return {"items": items if q.startswith("esp32") else items[1:2]}
    rows = rank(search(per_query=3, fetch=fake), now=NOW)
    order = [r["repository"] for r in rows]
    assert order.index("small/active") < order.index("old/stale")  # activity and breadth beat raw stars
    assert next(r for r in rows if r["repository"] == "big/unlicensed")["score"] == 0  # no licence, no use
    assert len(next(r for r in rows if r["repository"] == "small/active")["queries"]) > 1


def test_the_feed_is_pinned_and_admitted_as_discovered_only():
    rows = rank({"a/b": {"repo": _repo("a/b", 10, "2026-11-01T00:00:00Z", "MIT"), "categories": {"pinouts"}, "queries": {"x"}},
                 "c/d": {"repo": _repo("c/d", 10, "2026-11-01T00:00:00Z", None), "categories": {"pinouts"}, "queries": {"x"}}}, now=NOW)
    out = feed(rows, {"a/b": "a" * 40, "c/d": "b" * 40})
    assert [c["repository"] for c in out["candidates"]] == ["a/b"]  # the unlicensed one is left out
    normalized = normalize_feed(out)
    assert normalized[0]["discovered_only"] is True and normalized[0]["adapter_id"] is None


def test_the_recorded_sweep_feed_is_accepted_by_the_pipeline():
    sweep = json.loads((Path(__file__).resolve().parents[1] / "examples/github_signals/data_source_sweep_20261125.json").read_text())
    normalized = normalize_feed(sweep["feed"])
    assert 95 <= len(normalized) <= 100 and all(c["discovered_only"] for c in normalized)
    assert sweep["repositories_found"] > 400
