"""The fix-commit benchmark record keeps its honesty fields and its tallies consistent with its cases."""

from __future__ import annotations

import json
from pathlib import Path

RECORD = Path(__file__).resolve().parents[1] / "examples/schematic_bug_benchmark/fix_commit_benchmark_20261125.json"


def test_tallies_match_the_judged_cases_and_frozen_results_stay_separate():
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert "not independent evidence" in record["honesty"] and "root sheets" in record["honesty"]
    cases = record["cases"]
    assert record["cases_judged"] == len(cases)
    for checker, counts in record["tally"].items():
        assert counts["caught"] == sum(c["verdict"][checker].startswith("C") for c in cases)
        assert counts["partial"] == sum(c["verdict"][checker] == "P" for c in cases)
    # Current HS may only add to what frozen HS caught: a rule change must not lose an earlier catch.
    for case in cases:
        if case["verdict"]["hs_review_frozen"].startswith("C"):
            assert case["verdict"]["hs_review_current"].startswith("C"), case["fix_commit"]
    held = record["held_out_false_positives"]
    assert held["true"] + held["false"] == held["hs_findings"]
