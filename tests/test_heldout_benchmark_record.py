"""The held-out checker benchmark keeps its tallies equal to its judged cases and its honesty fields."""

import json
from pathlib import Path

RECORD = Path(__file__).resolve().parents[1] / "examples/schematic_bug_benchmark/heldout_benchmark_20261127.json"


def test_tallies_match_the_cases_and_the_independent_number_is_named():
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert record["role"] == "held_out" and "independent number" in record["honesty"]
    cases = record["cases"]
    assert record["cases_judged"] == len(cases) and record["excluded_count"] == len(record["excluded"])
    for checker, counts in record["tally"].items():
        assert counts["caught"] == sum(c["verdict"][checker] == "C" for c in cases), checker
    assert record["caught_by_any"] == sum(any(v == "C" for v in c["verdict"].values()) for c in cases)
    assert all(e["reason"] for e in record["excluded"])
    # A rule added after reading this set may only add catches, never lose one the dev-set rules had.
    for c in cases:
        if c["verdict"]["hs_review_dev_rules"] == "C":
            assert c["verdict"]["hs_review_current"] == "C", c["fix_commit"]
