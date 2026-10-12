"""The mutation benchmark must stay honest: mutants really apply, and only reviewed equivalents are excused."""
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "hardware_splicer" / "data" / "firmware_application" / "app_core.h"


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("bench_fault_matrix", ROOT / "scripts" / "benchmark_device_fault_matrix.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_fault_matrix"] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


def test_every_mutant_changes_exactly_one_place(bench):
    source = CORE.read_text(encoding="utf-8")
    for mutant in bench.MUTANTS + bench.HELDOUT_MUTANTS:
        assert bench.apply_mutant(source, mutant) != source, mutant.id


def test_mutant_ids_are_unique(bench):
    ids = [mutant.id for mutant in bench.MUTANTS + bench.HELDOUT_MUTANTS]
    assert len(ids) == len(set(ids))


def test_a_mutant_that_matches_nowhere_or_everywhere_is_refused(bench):
    source = "a b a"
    with pytest.raises(ValueError, match="0 places"):
        bench.apply_mutant(source, bench.Mutant("x", "c", "s", "zzz", "y"))
    with pytest.raises(ValueError, match="2 places"):
        bench.apply_mutant(source, bench.Mutant("x", "c", "s", "a", "y"))


def _row(bench, id, outcome, matrix, healthy=False, smoke=False, reason=""):
    return {
        "id": id, "bug_class": "c", "story": "", "outcome": outcome, "failing_scenarios": [],
        "detected_by": {"smoke": smoke, "healthy": healthy, "matrix": matrix},
        "equivalent_reason": reason, "detail": "",
    }


def test_only_a_reviewed_survivor_is_excused_and_a_kill_is_always_scored(bench):
    rows = [
        _row(bench, "killed", "KILLED", True, healthy=True, smoke=True),
        _row(bench, "gap", "SURVIVED", False),
        _row(bench, "equivalent", "SURVIVED", False, reason="unobservable because ..."),
        _row(bench, "wrongly_called_equivalent", "KILLED", True, reason="claimed unobservable"),
        _row(bench, "bad_mutant", "STILLBORN", False),
    ]
    summary = bench.summarize(rows)
    assert summary["reviewed_equivalent"] == ["equivalent"]
    assert summary["stillborn_compile_errors"] == ["bad_mutant"]
    assert summary["scored_mutants"] == 3  # killed, gap, wrongly_called_equivalent
    assert summary["survivors_without_review"] == ["gap"]
    assert summary["tiers"]["matrix"] == {"killed": 2, "of": 3, "score": 0.667}
    assert summary["caught_only_by_fault_scenarios"] == ["wrongly_called_equivalent"]


@pytest.mark.skipif(shutil.which("g++") is None, reason="needs a host compiler")
def test_clean_package_passes_and_a_seeded_bug_is_caught(bench, tmp_path):
    project = bench.build_package(tmp_path)
    assert bench.run_project(project)["outcome"] == "SURVIVED"
    mutant = next(m for m in bench.MUTANTS if m.id == "nan_not_rejected")
    row = bench.evaluate(mutant, project, tmp_path)
    assert row["outcome"] == "KILLED"
    assert row["detected_by"]["matrix"] is True
    assert row["detected_by"]["smoke"] is False  # a boot-only check cannot see it
