"""The mutation benchmark must stay honest: mutants really apply, and only reviewed equivalents are excused."""
import importlib.util
import shutil
import json
import subprocess
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


@pytest.mark.parametrize("part_id", ["adafruit-bme280-stemma-qt", "adafruit-bh1750-stemma-qt"])
def test_every_mutant_for_a_part_changes_exactly_one_place_in_its_own_target(bench, tmp_path, part_id):
    project = bench.build_package(tmp_path, part_id)
    pool = bench.MUTANTS + bench.HELDOUT_MUTANTS + bench.BH1750_TRAITS_MUTANTS
    applicable = [m for m in pool if m.part in ("", part_id)]
    assert len(applicable) == 48
    for mutant in applicable:
        source = (project / mutant.target).read_text(encoding="utf-8")
        assert bench.apply_mutant(source, mutant) != source, mutant.id


def test_part_specific_mutants_name_their_part_and_a_generated_header(bench):
    for mutant in bench.MUTANTS + bench.HELDOUT_MUTANTS + bench.BH1750_TRAITS_MUTANTS:
        assert (mutant.part == "") == (mutant.target == "src/app_core.h"), mutant.id


def test_mutant_ids_are_unique(bench):
    ids = [m.id for m in bench.MUTANTS + bench.HELDOUT_MUTANTS + bench.BH1750_TRAITS_MUTANTS]
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


def test_every_adapter_mutant_changes_exactly_one_place(bench, tmp_path):
    source = (bench.build_package(tmp_path) / "src" / "main.cpp").read_text(encoding="utf-8")
    mutants = bench.ADAPTER_MUTANTS + bench.ADAPTER_HELDOUT_MUTANTS
    for mutant in mutants:
        assert mutant.target == "src/main.cpp", mutant.id
        assert bench.apply_mutant(source, mutant) != source, mutant.id
    ids = [mutant.id for mutant in bench.MUTANTS + bench.HELDOUT_MUTANTS + mutants]
    assert len(ids) == len(set(ids))


def test_every_bh1750_adapter_mutant_changes_exactly_one_place_of_its_own_adapter(bench, tmp_path):
    source = (bench.build_package(tmp_path, bench.BH1750) / "src" / "main.cpp").read_text(encoding="utf-8")
    mutants = bench.adapter_mutants(bench.BH1750)
    assert len(mutants) == 39
    for mutant in mutants:
        assert mutant.target == "src/main.cpp", mutant.id
        assert bench.apply_mutant(source, mutant) != source, mutant.id
    own = bench.BH1750_ADAPTER_MUTANTS + bench.BH1750_ADAPTER_HELDOUT_MUTANTS
    assert all(m.part == bench.BH1750 for m in own)
    pool = bench.MUTANTS + bench.HELDOUT_MUTANTS + bench.ADAPTER_MUTANTS + bench.ADAPTER_HELDOUT_MUTANTS + own
    ids = [m.id for m in pool]
    assert len(ids) == len(set(ids))


def test_a_shared_adapter_mutant_is_excused_for_the_bh1750_only_with_a_reason_that_names_why(bench):
    bme = {m.id: m for m in bench.adapter_mutants(bench.BME280)}
    bh = {m.id: m for m in bench.adapter_mutants(bench.BH1750)}
    for mutant_id, reason in bench.BH1750_SHARED_EQUIVALENTS.items():
        assert bme[mutant_id].equivalent_reason == ""  # the same text is a real bug for the BME280's four-line display
        assert bh[mutant_id].equivalent_reason == reason and "pixel-identical" in reason
    for mutant in bench.BH1750_ADAPTER_MUTANTS + bench.BH1750_ADAPTER_HELDOUT_MUTANTS:
        assert not (mutant.equivalent_reason and mutant.blind_spot), mutant.id  # a survivor is one or the other


def _adapter_row(id, outcome, *, vendor_matrix, core_lane=False, equivalent="", blind_spot=""):
    return {
        "id": id, "bug_class": "c", "story": "", "outcome": outcome, "failing_scenarios": [],
        "detected_by": {"core_lane": core_lane, "vendor_smoke": False, "vendor_healthy": False, "vendor_matrix": vendor_matrix},
        "equivalent_reason": equivalent, "blind_spot": blind_spot, "detail": "",
    }


def test_adapter_summary_separates_equivalents_from_blind_spots_and_never_excuses_the_latter(bench):
    rows = [
        _adapter_row("killed", "KILLED", vendor_matrix=True),
        _adapter_row("equivalent", "SURVIVED", vendor_matrix=False, equivalent="redundant with the framework default"),
        _adapter_row("blind", "SURVIVED", vendor_matrix=False, blind_spot="the model has no start-up window"),
        _adapter_row("gap", "SURVIVED", vendor_matrix=False),
    ]
    summary = bench.summarize_adapter(rows)
    assert summary["reviewed_equivalent"] == ["equivalent"]
    assert summary["scored_mutants"] == 3  # a blind spot still counts against the score
    assert summary["known_host_model_blind_spots"] == ["blind"]
    assert summary["survivors_without_review"] == ["gap"]
    assert summary["tiers"]["vendor_matrix"]["killed"] == 1
    assert summary["tiers"]["core_lane"]["killed"] == 0


def _vendor_libs():
    import os

    named = os.environ.get("HS_VENDOR_LIBS", "").strip()
    return Path(named) if named else None


@pytest.mark.skipif(shutil.which("g++") is None, reason="needs a host compiler")
def test_adapter_lane_catches_a_seeded_adapter_bug_that_the_core_lane_cannot_see(bench, tmp_path):
    libs = _vendor_libs()
    if libs is None or not bench_libs_ok(libs):
        pytest.skip("pinned vendor libraries not available (set HS_VENDOR_LIBS to a PlatformIO libdeps directory)")
    project = bench.build_package(tmp_path)
    assert bench.run_vendor_project(project, libs.resolve())["outcome"] == "SURVIVED"
    mutant = next(m for m in bench.ADAPTER_MUTANTS if m.id == "adapter_pressure_unit_wrong")
    row = bench.evaluate_adapter(mutant, project, tmp_path, libs.resolve())
    assert row["outcome"] == "KILLED"
    assert row["detected_by"]["core_lane"] is False  # the core harness never compiles main.cpp


def bench_libs_ok(libs):
    from hardware_splicer.device_application_execution import vendor_libs_available

    return vendor_libs_available(libs)


@pytest.mark.parametrize("lane,part", [("core", "bme280"), ("vendor", "bme280"), ("vendor", "bh1750")])
@pytest.mark.parametrize("corruption", ["empty", "partial", "duplicate", "unknown", "non_object", "truthy", "finding", "bad_json", "exit"])
def test_benchmark_rejects_unsuccessful_or_incomplete_harness_runs(bench, tmp_path, monkeypatch, lane, part, corruption):
    from hardware_splicer.device_application_execution import HOST_SCENARIOS
    from hardware_splicer.device_vendor_profiles import vendor_profile

    project = bench.build_package(tmp_path, {"bme280": bench.BME280, "bh1750": bench.BH1750}[part])
    expected = HOST_SCENARIOS if lane == "core" else vendor_profile(part)["scenarios"]
    rows = [{"scenario": name, "pass": True} for name in expected]
    if corruption == "empty":
        rows = []
    elif corruption == "partial":
        rows = rows[:1]
    elif corruption == "duplicate":
        rows[-1] = rows[0]
    elif corruption == "unknown":
        rows[-1]["scenario"] = "unknown"
    elif corruption == "non_object":
        rows[-1] = []
    elif corruption == "truthy":
        rows[-1]["pass"] = 1
    elif corruption == "finding":
        rows[-1]["finding"] = True
    output = b"not JSON\n" if corruption == "bad_json" else b"".join((json.dumps(row) + "\n").encode() for row in rows)

    def execute(command, **kwargs):
        compiling = "-o" in command
        return subprocess.CompletedProcess(command, 0 if compiling or corruption != "exit" else 1,
                                           b"" if compiling else output, b"")

    # Before the repair the benchmark used raw subprocess.run; both paths receive the same controlled output.
    monkeypatch.setattr(bench.subprocess, "run", execute)
    monkeypatch.setattr(bench, "_execute", execute, raising=False)
    result = bench.run_project(project) if lane == "core" else bench.run_vendor_project(project, tmp_path)
    assert result["outcome"] == "KILLED"
    assert result["failed"] and result["detail"]


@pytest.mark.parametrize("lane,part", [("core", "bme280"), ("vendor", "bme280"), ("vendor", "bh1750")])
def test_complete_scenario_output_is_still_accepted_by_the_benchmark(bench, tmp_path, monkeypatch, lane, part):
    from hardware_splicer.device_application_execution import HOST_SCENARIOS
    from hardware_splicer.device_vendor_profiles import vendor_profile

    project = bench.build_package(tmp_path, {"bme280": bench.BME280, "bh1750": bench.BH1750}[part])
    expected = HOST_SCENARIOS if lane == "core" else vendor_profile(part)["scenarios"]
    output = b"".join((json.dumps({"scenario": name, "pass": True}) + "\n").encode() for name in expected)

    def execute(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, b"" if "-o" in command else output, b"")

    monkeypatch.setattr(bench.subprocess, "run", execute)
    monkeypatch.setattr(bench, "_execute", execute, raising=False)
    result = bench.run_project(project) if lane == "core" else bench.run_vendor_project(project, tmp_path)
    assert result["outcome"] == "SURVIVED"
